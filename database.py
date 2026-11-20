"""
database.py — SQLite layer for F-1 Job Hunter Agent
Handles init, deduplication, saving, and querying jobs.
"""

import sqlite3
import os
from datetime import date, datetime
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "jobs.db")


def init_db():
    """Create the jobs table if it doesn't already exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            url          TEXT    UNIQUE NOT NULL,
            title        TEXT,
            company      TEXT,
            location     TEXT,
            track        TEXT,       -- 'A' (ATS) or 'B' (BigTech)
            tier         TEXT,       -- '1', '2', '3', or 'other'
            ai_verdict   TEXT,       -- 'YES' or 'NO'
            scraped_date TEXT,       -- YYYY-MM-DD
            created_at   TEXT        -- ISO datetime
        )
    """)
    conn.commit()
    conn.close()


def is_seen(url: str) -> bool:
    """
    Return True only if this URL was already processed with a YES verdict.
    Jobs that were filtered (NO) are re-evaluated fresh on every run —
    this prevents dry-run contamination and allows re-checking of borderline cases.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM jobs WHERE url = ? AND ai_verdict = 'YES'", (url,))
    result = c.fetchone()
    conn.close()
    return result is not None


def save_job(job: dict):
    """
    Insert a new job record. Silently ignores duplicates.
    Expected keys: url, title, company, location, track, tier, ai_verdict
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO jobs (url, title, company, location, track, tier, ai_verdict, scraped_date, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job.get("url"),
            job.get("title", ""),
            job.get("company", ""),
            job.get("location", ""),
            job.get("track", "A"),
            job.get("tier", "other"),
            job.get("ai_verdict", "YES"),
            str(date.today()),
            datetime.now().isoformat(),
        ))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # URL already in DB — skip silently
    finally:
        conn.close()


def get_todays_yes_jobs(track: str) -> list:
    """
    Return all YES-verdict jobs from today for the given track.
    Sorted by company name then job title.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT title, company, location, url, tier
        FROM jobs
        WHERE track = ? AND ai_verdict = 'YES' AND scraped_date = ?
        ORDER BY
            CASE tier WHEN '1' THEN 1 WHEN '2' THEN 2 WHEN '3' THEN 3 ELSE 4 END,
            company, title
    """, (track, str(date.today())))
    rows = c.fetchall()
    conn.close()
    return [
        {"title": r[0], "company": r[1], "location": r[2], "url": r[3], "tier": r[4]}
        for r in rows
    ]


def get_stats_today() -> dict:
    """Return counts for today's run — used in the macOS notification."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = str(date.today())

    c.execute("SELECT COUNT(*) FROM jobs WHERE scraped_date = ?", (today,))
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM jobs WHERE scraped_date = ? AND ai_verdict = 'YES'", (today,))
    yes = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM jobs WHERE scraped_date = ? AND ai_verdict = 'YES' AND track = 'A'", (today,))
    ats = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM jobs WHERE scraped_date = ? AND ai_verdict = 'YES' AND track = 'B'", (today,))
    bigtech = c.fetchone()[0]

    conn.close()
    return {"total": total, "yes": yes, "ats": ats, "bigtech": bigtech}
