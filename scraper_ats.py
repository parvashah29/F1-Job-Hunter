"""
scraper_ats.py — Track A Scraper for F-1 Job Hunter Agent
Uses the public Greenhouse and Lever JSON APIs (no Playwright needed).
Filters job titles using role_matcher, then passes descriptions to the AI.
"""

import requests
import time
import logging
import random
import yaml
import os
from typing import Optional

import database
import ai_analyzer
import role_matcher
import location_filter

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


# ---------------------------------------------------------------------------
# Greenhouse helpers
# ---------------------------------------------------------------------------

def _fetch_greenhouse_jobs(slug: str) -> list:
    """
    Fetch all open positions from a company's Greenhouse board.
    Returns a list of dicts: {title, url, id, location}
    """
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        jobs = data.get("jobs", [])
        return [
            {
                "title": j.get("title", ""),
                "url": j.get("absolute_url", ""),
                "id": j.get("id"),
                "location": j.get("location", {}).get("name", ""),  # ← real location
            }
            for j in jobs
            if j.get("title") and j.get("absolute_url")
        ]
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            logger.warning(f"Greenhouse slug not found: {slug}")
        else:
            logger.error(f"Greenhouse HTTP error for {slug}: {e}")
    except Exception as e:
        logger.error(f"Greenhouse fetch error for {slug}: {e}")
    return []


def _fetch_greenhouse_description(slug: str, job_id: int) -> str:
    """Fetch the full job description text for a single Greenhouse job."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        # content is HTML — extract text naively
        content = data.get("content", "")
        # Strip HTML tags
        import re
        text = re.sub(r"<[^>]+>", " ", content)
        text = re.sub(r"\s+", " ", text).strip()
        return text
    except Exception as e:
        logger.warning(f"Could not fetch Greenhouse description for job {job_id}: {e}")
        return ""


# ---------------------------------------------------------------------------
# Lever helpers
# ---------------------------------------------------------------------------

def _fetch_lever_jobs(slug: str) -> list:
    """
    Fetch all open positions from a company's Lever board.
    Returns a list of dicts: {title, url, description, location}
    """
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        jobs = r.json()
        if not isinstance(jobs, list):
            return []
        return [
            {
                "title": j.get("text", ""),
                "url": j.get("hostedUrl", ""),
                "description": (
                    j.get("descriptionPlain", "") or
                    j.get("description", "")
                ),
                "location": (j.get("categories", {}) or {}).get("location", ""),
            }
            for j in jobs
            if j.get("text") and j.get("hostedUrl")
        ]
    except requests.exceptions.HTTPError as e:
        if e.response.status_code in (404, 403):
            logger.warning(f"Lever slug not found or private: {slug}")
        else:
            logger.error(f"Lever HTTP error for {slug}: {e}")
    except Exception as e:
        logger.error(f"Lever fetch error for {slug}: {e}")
    return []


# ---------------------------------------------------------------------------
# Main Track A runner
# ---------------------------------------------------------------------------

def run(config: dict, dry_run: bool = False) -> int:
    """
    Run Track A scraper.
    Returns the count of new YES jobs found.
    """
    ai_model = config.get("ai", {}).get("model", "llama3.2")
    ai_timeout = config.get("ai", {}).get("timeout_seconds", 45)
    track_a_cfg = config.get("track_a", {})
    gh_companies = track_a_cfg.get("greenhouse_companies", [])
    lv_companies = track_a_cfg.get("lever_companies", [])

    yes_count = 0
    total_seen = 0
    total_processed = 0

    logger.info(f"[Track A] Starting — {len(gh_companies)} Greenhouse + {len(lv_companies)} Lever companies")

    # ── Greenhouse ──────────────────────────────────────────────────────────
    for company in gh_companies:
        slug = company["slug"]
        name = company["name"]

        try:
            jobs = _fetch_greenhouse_jobs(slug)
            logger.info(f"[Track A] {name} (Greenhouse) — {len(jobs)} open positions")
        except Exception as e:
            logger.error(f"[Track A] Failed to fetch {name}: {e}")
            continue

        for job in jobs:
            title = job["title"]
            url = job["url"]
            job_id = job["id"]
            raw_location = job.get("location", "")

            # Pre-filter by role keyword
            tier = role_matcher.classify_tier(title)
            if tier is None:
                continue

            # ── Location filter — skip non-US/non-remote jobs ──
            if not location_filter.is_us_or_remote(raw_location):
                logger.debug(f"  ⏭️  Skipped (non-US location: {raw_location}): {title}")
                continue

            # Skip already seen jobs
            if database.is_seen(url):
                total_seen += 1
                continue

            total_processed += 1

            # Fetch full description for AI analysis
            description = _fetch_greenhouse_description(slug, job_id)
            time.sleep(random.uniform(0.3, 0.8))  # Be polite to the API

            # ── Fast YOE pre-filter — skip before calling Ollama ──
            if ai_analyzer.check_yoe_in_description(description):
                logger.info(f"  ⏭️  [YOE] Skipped high-experience role: {title} @ {name}")
                if not dry_run:
                    database.save_job({
                        "url": url, "title": title, "company": name,
                        "location": location_filter.clean_location(raw_location),
                        "track": "A", "tier": tier, "ai_verdict": "NO",
                    })
                continue

            verdict = "YES" if dry_run else ai_analyzer.analyze_job(
                description, model=ai_model, timeout=ai_timeout
            )

            job_record = {
                "url": url,
                "title": title,
                "company": name,
                "location": location_filter.clean_location(raw_location),
                "track": "A",
                "tier": tier,
                "ai_verdict": verdict,
            }

            if not dry_run:
                database.save_job(job_record)

            if verdict == "YES":
                yes_count += 1
                logger.info(f"  ✅ [{tier}] {title} @ {name}")
            else:
                logger.info(f"  ❌ [{tier}] {title} @ {name} — Filtered")

        # Small cooldown between companies
        time.sleep(random.uniform(1.0, 2.0))

    # ── Lever ───────────────────────────────────────────────────────────────
    for company in lv_companies:
        slug = company["slug"]
        name = company["name"]

        try:
            jobs = _fetch_lever_jobs(slug)
            logger.info(f"[Track A] {name} (Lever) — {len(jobs)} open positions")
        except Exception as e:
            logger.error(f"[Track A] Failed to fetch {name}: {e}")
            continue

        for job in jobs:
            title = job["title"]
            url = job["url"]
            description = job.get("description", "")
            raw_location = job.get("location", "")

            tier = role_matcher.classify_tier(title)
            if tier is None:
                continue

            # ── Location filter ──
            if not location_filter.is_us_or_remote(raw_location):
                logger.debug(f"  ⏭️  Skipped (non-US location: {raw_location}): {title}")
                continue

            if database.is_seen(url):
                total_seen += 1
                continue

            total_processed += 1

            # ── Fast YOE pre-filter ──
            if ai_analyzer.check_yoe_in_description(description):
                logger.info(f"  ⏭️  [YOE] Skipped high-experience role: {title} @ {name}")
                if not dry_run:
                    database.save_job({
                        "url": url, "title": title, "company": name,
                        "location": location_filter.clean_location(raw_location),
                        "track": "A", "tier": tier, "ai_verdict": "NO",
                    })
                continue

            verdict = "YES" if dry_run else ai_analyzer.analyze_job(
                description, model=ai_model, timeout=ai_timeout
            )

            job_record = {
                "url": url,
                "title": title,
                "company": name,
                "location": location_filter.clean_location(raw_location),
                "track": "A",
                "tier": tier,
                "ai_verdict": verdict,
            }

            if not dry_run:
                database.save_job(job_record)

            if verdict == "YES":
                yes_count += 1
                logger.info(f"  ✅ [{tier}] {title} @ {name}")
            else:
                logger.info(f"  ❌ [{tier}] {title} @ {name} — Filtered")

        time.sleep(random.uniform(0.5, 1.5))

    logger.info(
        f"[Track A] Done — Processed: {total_processed} new | Skipped (seen): {total_seen} | YES: {yes_count}"
    )
    return yes_count
