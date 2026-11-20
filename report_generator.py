"""
report_generator.py — Markdown report builder for F-1 Job Hunter Agent
Generates two daily reports from today's YES-verdict jobs in the DB.
"""

import os
import logging
from datetime import date, datetime

import database

logger = logging.getLogger(__name__)

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")

TIER_LABELS = {
    "1": "🥇 Tier 1 — Highest Priority",
    "2": "🥈 Tier 2 — Very Strong Match",
    "3": "🥉 Tier 3 — Good Opportunity",
    "other": "📌 Other",
}


def _group_by_tier(jobs: list) -> dict:
    """Group a flat list of jobs into a dict keyed by tier."""
    grouped = {"1": [], "2": [], "3": [], "other": []}
    for job in jobs:
        tier = job.get("tier", "other")
        grouped.setdefault(tier, []).append(job)
    return grouped


def _group_by_company(jobs: list) -> dict:
    """Group jobs by company name."""
    grouped = {}
    for job in jobs:
        company = job.get("company", "Unknown")
        grouped.setdefault(company, []).append(job)
    return grouped


# ---------------------------------------------------------------------------
# Track A Report
# ---------------------------------------------------------------------------

def generate_ats_report(max_jobs: int = 25) -> str:
    """
    Generate daily_jobs_YYYY-MM-DD.md for Track A (ATS/aggregator jobs).
    Returns the path to the created file.
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)
    today = str(date.today())
    filepath = os.path.join(REPORTS_DIR, f"daily_jobs_{today}.md")

    jobs = database.get_todays_yes_jobs("A")
    jobs = jobs[:max_jobs]
    grouped = _group_by_tier(jobs)

    now = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    total = len(jobs)

    lines = [
        f"# 🎯 Daily Job Digest — {today}",
        f"",
        f"> **Generated:** {now}  ",
        f"> **Track:** A — ATS & Aggregator (Greenhouse / Lever)  ",
        f"> **Total qualifying jobs:** {total}  ",
        f"> **How to use:** Review each listing carefully before applying. The AI defaults to YES when unsure — always check the full JD.",
        f"",
        "---",
        "",
    ]

    if total == 0:
        lines.append("_No new jobs found today matching your criteria. Check back tomorrow!_")
    else:
        job_num = 1
        for tier_key in ["1", "2", "3", "other"]:
            tier_jobs = grouped.get(tier_key, [])
            if not tier_jobs:
                continue

            lines.append(f"## {TIER_LABELS.get(tier_key, tier_key)}")
            lines.append("")

            for job in tier_jobs:
                title = job.get("title", "Unknown Title")
                company = job.get("company", "Unknown Company")
                location = job.get("location", "")
                url = job.get("url", "#")

                lines.append(f"### {job_num}. {title}")
                lines.append(f"**Company:** {company}  ")
                if location:
                    lines.append(f"**Location:** {location}  ")
                lines.append(f"**Apply:** [Open Application →]({url})  ")
                lines.append("")
                lines.append("---")
                lines.append("")
                job_num += 1

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"[Report] Track A report saved: {filepath} ({total} jobs)")
    return filepath


# ---------------------------------------------------------------------------
# Track B Report
# ---------------------------------------------------------------------------

def generate_bigtech_report(max_jobs: int = 30) -> str:
    """
    Generate bigtech_jobs_YYYY-MM-DD.md for Track B (Big Tech direct pages).
    Returns the path to the created file.
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)
    today = str(date.today())
    filepath = os.path.join(REPORTS_DIR, f"bigtech_jobs_{today}.md")

    jobs = database.get_todays_yes_jobs("B")
    jobs = jobs[:max_jobs]
    by_company = _group_by_company(jobs)
    total = len(jobs)

    now = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    lines = [
        f"# 🏢 Big Tech Job Digest — {today}",
        f"",
        f"> **Generated:** {now}  ",
        f"> **Track:** B — Big Tech Direct Career Pages  ",
        f"> **Total qualifying jobs:** {total}  ",
        f"> **Companies scraped:** {', '.join(by_company.keys()) or 'None'}",
        f"",
        "---",
        "",
    ]

    if total == 0:
        lines.append("_No Big Tech jobs found today matching your criteria. The companies may have posted nothing new, or anti-bot protections may have blocked scraping. Try again tomorrow._")
    else:
        # Sort companies so ones with more jobs appear first
        sorted_companies = sorted(by_company.items(), key=lambda x: -len(x[1]))

        for company, company_jobs in sorted_companies:
            lines.append(f"## 🏷️ {company}  ({len(company_jobs)} jobs)")
            lines.append("")

            # Sort within company by tier
            company_jobs_sorted = sorted(
                company_jobs,
                key=lambda j: {"1": 1, "2": 2, "3": 3}.get(j.get("tier", "3"), 4)
            )

            for job in company_jobs_sorted:
                title = job.get("title", "Unknown Title")
                location = job.get("location", "")
                url = job.get("url", "#")
                tier = job.get("tier", "?")
                tier_badge = {"1": "🥇", "2": "🥈", "3": "🥉"}.get(tier, "📌")

                lines.append(f"### {tier_badge} {title}")
                if location:
                    lines.append(f"📍 {location}  ")
                lines.append(f"🔗 [Apply Here →]({url})  ")
                lines.append("")

            lines.append("---")
            lines.append("")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"[Report] Track B report saved: {filepath} ({total} jobs)")
    return filepath


# ---------------------------------------------------------------------------
# Generate both reports
# ---------------------------------------------------------------------------

def generate_all(config: dict) -> tuple:
    """
    Generate both Track A and Track B reports.
    Returns (ats_path, bigtech_path).
    """
    limits = config.get("limits", {})
    ats_path = generate_ats_report(max_jobs=limits.get("track_a_report_max", 25))
    bt_path = generate_bigtech_report(max_jobs=limits.get("track_b_report_max", 30))
    return ats_path, bt_path
