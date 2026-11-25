"""
scraper_ats.py - Track A for F-1 Job Hunter.

Reads the public Greenhouse and Lever JSON job-board APIs (one request per company, no
HTML scraping, no login). Pipeline per job:
  role/tier match -> location filter -> dedup (SQLite) -> eligibility rules (+ optional LLM)
"""

import html
import logging
import random
import re
import time

import requests

import ai_analyzer
import database
import location_filter
import role_matcher
from http_util import DEFAULT_TIMEOUT, make_session

logger = logging.getLogger(__name__)

GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
LEVER_URL = "https://api.lever.co/v0/postings/{slug}?mode=json"


def html_to_text(raw: str) -> str:
    """Greenhouse returns entity-escaped HTML; unescape, drop tags, collapse whitespace."""
    text = html.unescape(raw or "")
    text = re.sub(r"<(?:br|/p|/li|/h\d)\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"[ \t\r\f\v]+", " ", re.sub(r"\n\s*", "\n", text)).strip()


# ---------------------------------------------------------------------------
# Fetchers - return a list of normalized dicts, or None if the fetch FAILED
# (None vs [] matters: only a successful fetch may mark vanished jobs as removed)
# ---------------------------------------------------------------------------

def _get_json(session, url, label):
    try:
        r = session.get(url, timeout=DEFAULT_TIMEOUT)
        if r.status_code in (403, 404):
            logger.warning(f"[Track A] {label}: board not found or private (HTTP {r.status_code})")
            return None
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError) as e:
        logger.error(f"[Track A] {label}: fetch failed ({type(e).__name__}: {e})")
        return None


def fetch_greenhouse(session, slug: str):
    data = _get_json(session, GREENHOUSE_URL.format(slug=slug), f"{slug} (Greenhouse)")
    if not isinstance(data, dict):
        return None
    out = []
    for j in data.get("jobs", []):
        if not (j.get("title") and j.get("absolute_url")):
            continue
        out.append({
            "title": j["title"].strip(),
            "url": j["absolute_url"],
            "location": ((j.get("location") or {}).get("name") or "").strip(),
            "description": html_to_text(j.get("content", "")),
        })
    return out


def fetch_lever(session, slug: str):
    data = _get_json(session, LEVER_URL.format(slug=slug), f"{slug} (Lever)")
    if not isinstance(data, list):
        return None
    out = []
    for j in data:
        if not (j.get("text") and j.get("hostedUrl")):
            continue
        parts = [j.get("descriptionPlain") or html_to_text(j.get("description", ""))]
        for lst in j.get("lists") or []:
            parts.append(lst.get("text", ""))
            parts.append(html_to_text(lst.get("content", "")))
        parts.append(j.get("additionalPlain") or html_to_text(j.get("additional", "")))
        out.append({
            "title": j["text"].strip(),
            "url": j["hostedUrl"],
            "location": ((j.get("categories") or {}).get("location") or "").strip(),
            "description": "\n".join(p for p in parts if p),
        })
    return out


# ---------------------------------------------------------------------------
# Per-company processing
# ---------------------------------------------------------------------------

def process_company(name: str, jobs: list, ai_cfg: dict, dry_run: bool, stats: dict, track="A"):
    """Filter/score one company's jobs; appends accepted ones to stats['found']."""
    use_llm = not dry_run
    for job in jobs:
        title, url, raw_loc = job["title"], job["url"], job["location"]
        tier = role_matcher.classify_tier(title)
        if tier is None:
            stats["role_skipped"] += 1
            continue
        if not location_filter.is_us_or_remote(raw_loc):
            stats["location_skipped"] += 1
            continue

        existing = None if dry_run else database.get_job(url)
        if existing and existing.get("reason") is not None and existing["title"] == title:
            database.touch_job(url)
            stats["seen"] += 1
            continue

        verdict, reason = ai_analyzer.decide(job["description"], ai_cfg, use_llm=use_llm)
        record = {
            "url": url, "title": title, "company": name,
            "location": location_filter.clean_location(raw_loc),
            "track": track, "tier": tier, "ai_verdict": verdict, "reason": reason,
        }
        change = "new" if dry_run else database.save_job(record)
        if change == "changed":
            stats["changed"] += 1
        stats["processed"] += 1
        if verdict == "YES":
            stats["yes"] += 1
            stats["found"].append(record)
            logger.info(f"  [YES][T{tier}] {title} @ {name} ({reason})")
        else:
            stats["no"] += 1
            logger.info(f"  [NO ][T{tier}] {title} @ {name} ({reason})")


def run(config: dict, dry_run: bool = False, limit: int = None, session=None) -> dict:
    """
    Run Track A. `limit` caps the number of companies scraped (useful for smoke tests).
    Returns a stats dict (see `stats` below); never raises for a single company's failure.
    """
    cfg = config.get("track_a", {}) or {}
    ai_cfg = config.get("ai", {}) or {}
    delay = float(cfg.get("request_delay_seconds", 1.0))
    session = session or make_session()

    boards = [("Greenhouse", c) for c in cfg.get("greenhouse_companies", []) or []] + \
             [("Lever", c) for c in cfg.get("lever_companies", []) or []]
    boards = [(k, c) for k, c in boards if c.get("enabled", True)]
    if limit:
        boards = boards[:limit]

    stats = {"companies_ok": 0, "companies_failed": [], "fetched": 0, "processed": 0,
             "seen": 0, "yes": 0, "no": 0, "changed": 0, "removed": 0,
             "role_skipped": 0, "location_skipped": 0, "found": []}
    logger.info(f"[Track A] Starting - {len(boards)} boards{' (dry run)' if dry_run else ''}")

    for i, (kind, company) in enumerate(boards):
        slug, name = company["slug"], company.get("name", company["slug"])
        try:
            fetch = fetch_greenhouse if kind == "Greenhouse" else fetch_lever
            jobs = fetch(session, slug)
            if jobs is None:
                stats["companies_failed"].append(name)
            else:
                stats["companies_ok"] += 1
                stats["fetched"] += len(jobs)
                logger.info(f"[Track A] {name} ({kind}) - {len(jobs)} open positions")
                process_company(name, jobs, ai_cfg, dry_run, stats)
                if not dry_run:
                    stats["removed"] += database.mark_removed("A", name, [j["url"] for j in jobs])
        except Exception as e:  # isolate every company
            logger.error(f"[Track A] {name}: unexpected error {type(e).__name__}: {e}")
            stats["companies_failed"].append(name)
        if i < len(boards) - 1:
            time.sleep(delay * random.uniform(0.8, 1.4))

    logger.info(
        f"[Track A] Done - boards ok {stats['companies_ok']}/{len(boards)}, fetched {stats['fetched']}, "
        f"new evaluated {stats['processed']} (YES {stats['yes']}, NO {stats['no']}), "
        f"already seen {stats['seen']}, changed {stats['changed']}, removed {stats['removed']}"
    )
    return stats
