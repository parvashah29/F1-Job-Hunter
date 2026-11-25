"""
scraper_bigtech.py — Track B Scraper for F-1 Job Hunter Agent
Uses Playwright to scrape official career pages of major tech companies.
Each company has a dedicated extractor function due to unique HTML structures.
"""

import time
import random
import logging
import re
import os
import urllib.robotparser
from urllib.parse import urlparse
from typing import Optional

try:  # Playwright is optional: Track A works without it
    from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout
    PLAYWRIGHT_OK = True
except ImportError:  # pragma: no cover
    sync_playwright = None
    Page = object
    PWTimeout = TimeoutError
    PLAYWRIGHT_OK = False

import database
import ai_analyzer
import role_matcher
import location_filter
from http_util import USER_AGENT

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

def _human_delay(min_s: float = 2.0, max_s: float = 5.0):
    time.sleep(random.uniform(min_s, max_s))


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()


def _safe_text(page: Page, selector: str, default: str = "") -> str:
    try:
        el = page.query_selector(selector)
        return el.inner_text().strip() if el else default
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Company-specific extractors
# ---------------------------------------------------------------------------

def _extract_meta(page: Page, base_url: str) -> list:
    """Extract job listings from Meta Careers."""
    jobs = []
    try:
        page.wait_for_selector('[data-testid="job_listing_job_title"]', timeout=15000)
    except PWTimeout:
        # Try alternative selector
        try:
            page.wait_for_selector('a[href*="/jobs/"]', timeout=10000)
        except PWTimeout:
            logger.warning("[Meta] Timed out waiting for job listings")
            return jobs

    cards = page.query_selector_all('[data-testid="job_listing_job_title"]')
    if not cards:
        # Fallback: any link that looks like a job posting
        cards = page.query_selector_all('a[href*="/jobs/"]')

    seen_urls = set()
    for card in cards[:30]:
        try:
            title = card.inner_text().strip()
            href = card.get_attribute("href") or ""
            url = href if href.startswith("http") else f"{base_url}{href}"
            if url not in seen_urls and title:
                seen_urls.add(url)
                jobs.append({"title": title, "url": url, "company": "Meta", "location": "United States"})
        except Exception:
            continue
    return jobs


def _extract_amazon(page: Page, base_url: str) -> list:
    """Extract job listings from Amazon Jobs."""
    jobs = []
    try:
        page.wait_for_selector('.job-tile', timeout=15000)
    except PWTimeout:
        try:
            page.wait_for_selector('[data-test="job-title"]', timeout=10000)
        except PWTimeout:
            logger.warning("[Amazon] Timed out waiting for job listings")
            return jobs

    # Try multiple card selectors Amazon uses
    cards = page.query_selector_all('.job-tile')
    if not cards:
        cards = page.query_selector_all('.result')

    seen_urls = set()
    for card in cards[:30]:
        try:
            # Title
            title_el = (
                card.query_selector('h3') or
                card.query_selector('[data-test="job-title"]') or
                card.query_selector('a')
            )
            title = title_el.inner_text().strip() if title_el else ""

            # URL
            link_el = card.query_selector('a')
            href = link_el.get_attribute("href") if link_el else ""
            url = href if href.startswith("http") else f"{base_url}{href}"

            # Location
            loc_el = card.query_selector('.location-icon + span') or card.query_selector('.job-location')
            location = loc_el.inner_text().strip() if loc_el else "United States"

            if url not in seen_urls and title:
                seen_urls.add(url)
                jobs.append({"title": title, "url": url, "company": "Amazon", "location": location})
        except Exception:
            continue
    return jobs


def _extract_google(page: Page, base_url: str) -> list:
    """Extract job listings from Google Careers."""
    jobs = []
    try:
        page.wait_for_selector('li[class*="sMn82b"]', timeout=20000)
    except PWTimeout:
        try:
            page.wait_for_selector('[jsname="N9EaGc"]', timeout=10000)
        except PWTimeout:
            logger.warning("[Google] Timed out waiting for job listings")
            return jobs

    # Google uses obfuscated class names — try broad selector
    cards = (
        page.query_selector_all('li[class*="sMn82b"]') or
        page.query_selector_all('.sMn82b') or
        page.query_selector_all('ul.lLDsNb > li')
    )

    seen_urls = set()
    for card in cards[:30]:
        try:
            title_el = card.query_selector('h3') or card.query_selector('[class*="QJPWVe"]')
            title = title_el.inner_text().strip() if title_el else ""

            link_el = card.query_selector('a')
            href = link_el.get_attribute("href") if link_el else ""
            url = href if href.startswith("http") else f"{base_url}{href}"

            loc_el = card.query_selector('[class*="r0wTof"]') or card.query_selector('span[class*="location"]')
            location = loc_el.inner_text().strip() if loc_el else "United States"

            if url not in seen_urls and title:
                seen_urls.add(url)
                jobs.append({"title": title, "url": url, "company": "Google", "location": location})
        except Exception:
            continue
    return jobs


def _extract_microsoft(page: Page, base_url: str) -> list:
    """Extract job listings from Microsoft Careers."""
    jobs = []
    try:
        page.wait_for_selector('.ms-List-cell', timeout=20000)
    except PWTimeout:
        try:
            page.wait_for_selector('[aria-label*="job"]', timeout=10000)
        except PWTimeout:
            logger.warning("[Microsoft] Timed out waiting for job listings")
            return jobs

    cards = page.query_selector_all('.ms-List-cell')
    if not cards:
        cards = page.query_selector_all('[class*="JobCard"]')

    seen_urls = set()
    for card in cards[:30]:
        try:
            title_el = card.query_selector('h2') or card.query_selector('a')
            title = title_el.inner_text().strip() if title_el else ""

            link_el = card.query_selector('a')
            href = link_el.get_attribute("href") if link_el else ""
            url = href if href.startswith("http") else f"{base_url}{href}"

            loc_el = card.query_selector('[class*="location"]') or card.query_selector('[aria-label*="location"]')
            location = loc_el.inner_text().strip() if loc_el else "United States"

            if url not in seen_urls and title:
                seen_urls.add(url)
                jobs.append({"title": title, "url": url, "company": "Microsoft", "location": location})
        except Exception:
            continue
    return jobs


def _extract_apple(page: Page, base_url: str) -> list:
    """Extract job listings from Apple Jobs."""
    jobs = []
    try:
        page.wait_for_selector('.table--advanced-search__title', timeout=20000)
    except PWTimeout:
        try:
            page.wait_for_selector('a[href*="/en-us/details/"]', timeout=10000)
        except PWTimeout:
            logger.warning("[Apple] Timed out waiting for job listings")
            return jobs

    cards = page.query_selector_all('.table--advanced-search__title')
    if not cards:
        cards = page.query_selector_all('a[href*="/en-us/details/"]')

    seen_urls = set()
    for card in cards[:30]:
        try:
            title = card.inner_text().strip()
            href = card.get_attribute("href") or ""
            url = href if href.startswith("http") else f"{base_url}{href}"
            if url not in seen_urls and title:
                seen_urls.add(url)
                jobs.append({"title": title, "url": url, "company": "Apple", "location": "United States"})
        except Exception:
            continue
    return jobs


def _extract_generic(page: Page, company_name: str, base_url: str) -> list:
    """
    Generic fallback extractor — tries common job listing patterns.
    Used for NVIDIA (Workday), Netflix, OpenAI, Salesforce, Adobe.
    """
    jobs = []
    # Wait for any content to load
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except PWTimeout:
        pass

    _human_delay(1, 2)

    # Try these selectors in order
    selectors_to_try = [
        'a[href*="job"]',
        'a[href*="career"]',
        'a[href*="position"]',
        'a[href*="posting"]',
        '[class*="job"] a',
        '[class*="role"] a',
        '[class*="position"] a',
        'h3 a', 'h2 a', 'li a',
    ]

    seen_urls = set()
    for selector in selectors_to_try:
        links = page.query_selector_all(selector)
        if len(links) >= 3:  # Found a meaningful number of links
            for link in links[:30]:
                try:
                    title = link.inner_text().strip()
                    href = link.get_attribute("href") or ""
                    # Filter noise — only include links with reasonable titles
                    if len(title) < 5 or len(title) > 120:
                        continue
                    url = href if href.startswith("http") else f"{base_url}{href}"
                    if url not in seen_urls and title and href:
                        seen_urls.add(url)
                        jobs.append({
                            "title": title,
                            "url": url,
                            "company": company_name,
                            "location": "United States",
                        })
                except Exception:
                    continue
            if jobs:
                break  # Found jobs, stop trying selectors

    return jobs


def _get_job_description(page: Page, url: str) -> str:
    """Navigate to a job detail page and extract the description text."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        _human_delay(1.5, 3.0)

        # Common description containers
        selectors = [
            '[data-testid="job-description"]',
            '#job-description',
            '.job-description',
            '[class*="description"]',
            '[class*="content"]',
            'article',
            'main',
        ]
        for sel in selectors:
            el = page.query_selector(sel)
            if el:
                text = el.inner_text().strip()
                if len(text) > 100:
                    return text[:4000]

        # Final fallback — get all body text
        body = page.query_selector("body")
        if body:
            return body.inner_text().strip()[:4000]

    except PWTimeout:
        logger.warning(f"Timed out loading job detail: {url}")
    except Exception as e:
        logger.warning(f"Error loading job detail {url}: {e}")

    return ""


# ---------------------------------------------------------------------------
# Company dispatcher
# ---------------------------------------------------------------------------

EXTRACTOR_MAP = {
    "Meta":      _extract_meta,
    "Amazon":    _extract_amazon,
    "Google":    _extract_google,
    "Microsoft": _extract_microsoft,
    "Apple":     _extract_apple,
}


# ---------------------------------------------------------------------------
# Main Track B runner
# ---------------------------------------------------------------------------

_robots_cache = {}


def robots_allows(url: str) -> bool:
    """Respect robots.txt for the search URL. If robots.txt is unreachable, allow (standard)."""
    parts = urlparse(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    rp = _robots_cache.get(origin)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        try:
            import requests
            r = requests.get(origin + "/robots.txt", timeout=10, headers={"User-Agent": USER_AGENT})
            if r.status_code == 200:
                rp.parse(r.text.splitlines())
            else:
                rp.parse([])  # no robots.txt -> allow all
        except Exception:
            rp.parse([])
        _robots_cache[origin] = rp
    return rp.can_fetch(USER_AGENT, url)


def run(config: dict, dry_run: bool = False, limit: int = None, only: list = None) -> dict:
    """
    Run Track B. Every site is isolated: a failure is logged and recorded in
    stats['results'][site], never raised. `limit` caps jobs processed per site.
    Sites with `enabled: false` in config are skipped; nothing here tries to evade bot
    protection - a blocked site should be disabled instead.
    """
    cfg = config.get("track_b", {}) or {}
    ai_cfg = config.get("ai", {}) or {}
    page_timeout = cfg.get("page_load_timeout", 30000)
    min_delay = cfg.get("min_delay_seconds", 2)
    max_delay = cfg.get("max_delay_seconds", 5)
    max_per_co = limit or cfg.get("max_jobs_per_company", 15)

    stats = {"yes": 0, "no": 0, "processed": 0, "results": {}, "found": []}
    companies = [c for c in cfg.get("companies", []) or []]
    if only:
        companies = [c for c in companies if c["name"].lower() in {o.lower() for o in only}]

    if not PLAYWRIGHT_OK:
        logger.error("[Track B] Playwright is not installed. Run: pip install playwright && "
                     "playwright install chromium  (or use --track a)")
        stats["error"] = "playwright-missing"
        return stats

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=True)
        except Exception as e:
            logger.error(f"[Track B] Cannot launch Chromium ({type(e).__name__}). "
                         "Run: playwright install chromium")
            stats["error"] = "chromium-missing"
            return stats
        try:
            context = browser.new_context(user_agent=USER_AGENT, viewport={"width": 1440, "height": 900})
            for company_cfg in companies:
                name = company_cfg["name"]
                if not company_cfg.get("enabled", True):
                    stats["results"][name] = "disabled in config" + (
                        f" ({company_cfg['disabled_reason']})" if company_cfg.get("disabled_reason") else "")
                    logger.info(f"[Track B] {name}: disabled in config - skipping")
                    continue
                try:
                    stats["results"][name] = _scrape_site(
                        context, company_cfg, ai_cfg, dry_run, stats,
                        page_timeout, min_delay, max_delay, max_per_co)
                except Exception as e:  # isolate every site
                    stats["results"][name] = f"error: {type(e).__name__}"
                    logger.error(f"[Track B] {name}: failed - {type(e).__name__}: {e}")
                _human_delay(min_delay, max_delay)
        finally:
            browser.close()

    logger.info(f"[Track B] Done - YES: {stats['yes']}, NO: {stats['no']}")
    return stats


def _scrape_site(context, company_cfg, ai_cfg, dry_run, stats,
                 page_timeout, min_delay, max_delay, max_per_co) -> str:
    """Scrape one site. Returns a short human-readable status string."""
    name = company_cfg["name"]
    search_url = company_cfg["search_url"]
    base_url = company_cfg["base_url"]

    if not robots_allows(search_url):
        logger.warning(f"[Track B] {name}: robots.txt disallows {search_url} - skipping")
        return "skipped (robots.txt disallows)"

    page = context.new_page()
    page.set_default_timeout(page_timeout)
    try:
        logger.info(f"[Track B] Scraping {name}...")
        try:
            page.goto(search_url, wait_until="domcontentloaded", timeout=page_timeout)
        except PWTimeout:
            logger.warning(f"[Track B] {name}: page load timed out")
            return "failed: page load timed out"
        except Exception as e:
            logger.error(f"[Track B] {name}: navigation error - {type(e).__name__}")
            return f"failed: navigation error ({type(e).__name__})"
        _human_delay(min_delay, max_delay)

        extractor = EXTRACTOR_MAP.get(name) or (lambda pg, bu: _extract_generic(pg, name, bu))
        listings = extractor(page, base_url)
        logger.info(f"[Track B] {name} - {len(listings)} job listings found")
        if not listings:
            return "0 listings (blocked, layout changed, or empty results)"

        processed = 0
        for job in listings:
            if processed >= max_per_co:
                break
            title = re.sub(r"\s+", " ", job["title"]).strip()
            url, raw_loc = job["url"].strip(), job.get("location", "")
            if len(title) > 140 or re.match(r"(?i)^(apply|view|learn more|read more|see all)", title):
                continue
            tier = role_matcher.classify_tier(title)
            if tier is None or not location_filter.is_us_or_remote(raw_loc):
                continue
            existing = None if dry_run else database.get_job(url)
            if existing and existing.get("reason") is not None and existing["title"] == title:
                database.touch_job(url)
                continue
            description = "" if dry_run else _get_job_description(page, url)
            _human_delay(min_delay, max_delay)
            verdict, reason = ai_analyzer.decide(description, ai_cfg, use_llm=not dry_run)
            record = {"url": url, "title": title, "company": name,
                      "location": location_filter.clean_location(raw_loc),
                      "track": "B", "tier": tier, "ai_verdict": verdict, "reason": reason}
            if not dry_run:
                database.save_job(record)
            processed += 1
            stats["processed"] += 1
            if verdict == "YES":
                stats["yes"] += 1
                stats["found"].append(record)
                logger.info(f"  [YES][T{tier}] {title} @ {name} ({reason})")
            else:
                stats["no"] += 1
                logger.info(f"  [NO ][T{tier}] {title} @ {name} ({reason})")
        return f"ok: {len(listings)} listings, {processed} evaluated"
    finally:
        try:
            page.close()
        except Exception:
            pass
