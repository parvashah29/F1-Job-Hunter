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
from typing import Optional

from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout

import database
import ai_analyzer
import role_matcher
import location_filter

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

def run(config: dict, dry_run: bool = False) -> int:
    """
    Run Track B (Big Tech) scraper.
    Returns count of new YES jobs found.
    """
    ai_model = config.get("ai", {}).get("model", "llama3.2")
    ai_timeout = config.get("ai", {}).get("timeout_seconds", 45)
    track_b_cfg = config.get("track_b", {})
    companies = track_b_cfg.get("companies", [])
    page_timeout = track_b_cfg.get("page_load_timeout", 30000)
    min_delay = track_b_cfg.get("min_delay_seconds", 2)
    max_delay = track_b_cfg.get("max_delay_seconds", 5)
    max_per_co = track_b_cfg.get("max_jobs_per_company", 15)

    yes_count = 0
    logger.info(f"[Track B] Starting — {len(companies)} Big Tech companies to scrape")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
        )

        for company_cfg in companies:
            name = company_cfg["name"]
            search_url = company_cfg["search_url"]
            base_url = company_cfg["base_url"]

            # ── Each company gets its own fresh page ──────────────────────
            # This prevents a redirect/error on one site from cascading into
            # the next company's navigation (the bug that caused 0 jobs).
            page = context.new_page()
            page.set_default_timeout(page_timeout)

            try:
                logger.info(f"[Track B] Scraping {name}...")
                try:
                    page.goto(search_url, wait_until="domcontentloaded", timeout=page_timeout)
                    _human_delay(min_delay, max_delay)
                except PWTimeout:
                    logger.warning(f"[Track B] {name}: Page load timed out — skipping")
                    continue
                except Exception as e:
                    logger.error(f"[Track B] {name}: Navigation error — {e}")
                    continue

                # Use company-specific extractor if available, else fallback
                extractor = EXTRACTOR_MAP.get(name, lambda pg, bu: _extract_generic(pg, name, bu))
                try:
                    job_listings = extractor(page, base_url)
                except Exception as e:
                    logger.error(f"[Track B] {name}: Extractor error — {e}")
                    job_listings = []

                logger.info(f"[Track B] {name} — {len(job_listings)} job listings found")

                processed = 0
                for job in job_listings:
                    if processed >= max_per_co:
                        break

                    title = job.get("title", "").strip()
                    url = job.get("url", "").strip()
                    raw_location = job.get("location", "")

                    if not title or not url:
                        continue

                    # Pre-filter by role keyword
                    tier = role_matcher.classify_tier(title)
                    if tier is None:
                        continue

                    # Location filter
                    if not location_filter.is_us_or_remote(raw_location):
                        logger.debug(f"  ⏭️  Skipped (non-US): {title} @ {name}")
                        continue

                    # Dedup check
                    if database.is_seen(url):
                        continue

                    # Fetch full description
                    description = "" if dry_run else _get_job_description(page, url)
                    _human_delay(min_delay, max_delay)

                    # YOE pre-filter
                    if not dry_run and ai_analyzer.check_yoe_in_description(description):
                        logger.info(f"  ⏭️  [YOE] Skipped: {title} @ {name}")
                        database.save_job({
                            "url": url, "title": title, "company": name,
                            "location": location_filter.clean_location(raw_location),
                            "track": "B", "tier": tier, "ai_verdict": "NO",
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
                        "track": "B",
                        "tier": tier,
                        "ai_verdict": verdict,
                    }

                    if not dry_run:
                        database.save_job(job_record)

                    if verdict == "YES":
                        yes_count += 1
                        logger.info(f"  ✅ [T{tier}] {title} @ {name}")
                    else:
                        logger.info(f"  ❌ [T{tier}] {title} @ {name} — Filtered")

                    processed += 1

                    # Navigate back to search results for next job
                    try:
                        page.go_back(wait_until="domcontentloaded", timeout=10000)
                        _human_delay(1, 2)
                    except Exception:
                        try:
                            page.goto(search_url, wait_until="domcontentloaded", timeout=page_timeout)
                            _human_delay(min_delay, max_delay)
                        except Exception:
                            break

            finally:
                # Always close this company's page — even on error — so the
                # next company starts with a clean slate
                try:
                    page.close()
                except Exception:
                    pass

            # Cooldown between companies
            _human_delay(min_delay + 1, max_delay + 2)

        context.close()
        browser.close()

    logger.info(f"[Track B] Done — YES: {yes_count}")
    return yes_count
