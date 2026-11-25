"""
report_generator.py - Markdown reports for F-1 Job Hunter.

Reports are built from the SQLite DB (active YES jobs first seen within `since_days`).
"""

import logging
import os
import re
from datetime import date, datetime

import database

logger = logging.getLogger(__name__)

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")

TIER_LABELS = {
    "1": "Tier 1 - Highest priority",
    "2": "Tier 2 - Strong match",
    "3": "Tier 3 - Good opportunity",
    "other": "Other",
}


def _md(text: str) -> str:
    """Escape characters that would break a Markdown link label."""
    return re.sub(r"([\[\]])", r"\\\1", text or "")


def _group(jobs, key):
    grouped = {}
    for j in jobs:
        grouped.setdefault(j.get(key) or "other", []).append(j)
    return grouped


def render_ats_report(jobs: list, since_days: int = 0, meta: dict = None, removed: list = None) -> str:
    meta = meta or {}
    today = str(date.today())
    window = "today" if since_days == 0 else f"the last {since_days + 1} days"
    lines = [
        f"# Daily Job Digest - {today}",
        "",
        f"> **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ",
        "> **Track:** A - Greenhouse / Lever public job-board APIs  ",
        f"> **New matching jobs (first seen {window}):** {len(jobs)}  ",
        "> **Note:** Eligibility is keyword-rule based (and optionally a local LLM). "
        "Unclear postings default to YES - always read the full posting.",
        "",
    ]
    if meta:
        lines += [
            "## Run summary", "",
            f"- Boards fetched OK: {meta.get('companies_ok', '?')}"
            f" (failed: {len(meta.get('companies_failed', []))})",
            f"- Postings fetched: {meta.get('fetched', '?')}; newly evaluated: {meta.get('processed', '?')};"
            f" already seen: {meta.get('seen', '?')}",
            f"- Rejected by rules: {meta.get('no', '?')}; skipped (role/location):"
            f" {meta.get('role_skipped', 0)}/{meta.get('location_skipped', 0)}",
        ]
        if meta.get("companies_failed"):
            lines.append(f"- Failed boards: {', '.join(meta['companies_failed'])}")
        lines.append("")
    lines += ["---", ""]

    if not jobs:
        lines.append(f"_No new matching jobs first seen {window}._")
    else:
        grouped = _group(jobs, "tier")
        n = 1
        for tier in ("1", "2", "3", "other"):
            tier_jobs = grouped.get(tier, [])
            if not tier_jobs:
                continue
            lines += [f"## {TIER_LABELS[tier]} ({len(tier_jobs)})", ""]
            for j in tier_jobs:
                loc = f" - {j['location']}" if j.get("location") else ""
                lines.append(f"{n}. **[{_md(j['title'])}]({j['url']})** - {j['company']}{loc}")
                n += 1
            lines.append("")

    if removed:
        lines += ["---", "", f"## No longer listed ({len(removed)})", "",
                  "_Previously reported jobs that disappeared from their board._", ""]
        lines += [f"- {_md(r['title'])} - {r['company']}" for r in removed[:50]]
        lines.append("")
    return "\n".join(lines)


def render_bigtech_report(jobs: list, since_days: int = 0, meta: dict = None) -> str:
    meta = meta or {}
    today = str(date.today())
    window = "today" if since_days == 0 else f"the last {since_days + 1} days"
    lines = [
        f"# Big Tech Job Digest - {today}",
        "",
        f"> **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ",
        "> **Track:** B - Big Tech career pages (Playwright, best effort)  ",
        f"> **New matching jobs (first seen {window}):** {len(jobs)}",
        "",
    ]
    if meta.get("results"):
        lines += ["## Site status", ""]
        for name, r in meta["results"].items():
            lines.append(f"- {name}: {r}")
        lines.append("")
    lines += ["---", ""]
    if not jobs:
        lines.append("_No Big Tech jobs found. Career sites often block automation or change "
                     "their layout; see the site status above and the log._")
    else:
        by_co = _group(jobs, "company")
        for company, cjobs in sorted(by_co.items(), key=lambda kv: -len(kv[1])):
            lines += [f"## {company} ({len(cjobs)})", ""]
            for j in cjobs:
                loc = f" - {j['location']}" if j.get("location") else ""
                lines.append(f"- [T{j.get('tier', '?')}] **[{_md(j['title'])}]({j['url']})**{loc}")
            lines.append("")
    return "\n".join(lines)


def _write(name: str, content: str) -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = os.path.join(REPORTS_DIR, f"{name}_{date.today()}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def generate_all(config: dict, since_days: int = 0, ats_meta: dict = None, bt_meta: dict = None) -> tuple:
    """Write both reports from the DB. Returns (ats_path, bigtech_path)."""
    limits = config.get("limits", {}) or {}
    ats_jobs = database.get_new_yes_jobs("A", since_days)[: limits.get("track_a_report_max", 25) or None]
    bt_jobs = database.get_new_yes_jobs("B", since_days)[: limits.get("track_b_report_max", 30) or None]
    removed = database.get_removed_since(since_days)
    ats_path = _write("daily_jobs", render_ats_report(ats_jobs, since_days, ats_meta, removed))
    bt_path = _write("bigtech_jobs", render_bigtech_report(bt_jobs, since_days, bt_meta))
    logger.info(f"[Report] wrote {ats_path} ({len(ats_jobs)} jobs) and {bt_path} ({len(bt_jobs)} jobs)")
    return ats_path, bt_path
