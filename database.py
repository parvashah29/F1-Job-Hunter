"""
database.py - SQLite layer for F-1 Job Hunter.

Schema is versioned via PRAGMA user_version and migrated additively, so an
existing data/jobs.db from older versions keeps working:
  v1 (legacy): jobs(url, title, company, location, track, tier, ai_verdict, scraped_date, created_at)
  v2: + last_seen, active, reason, updated_at
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta

DB_PATH = os.environ.get("F1_DB_PATH") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "jobs.db"
)
SCHEMA_VERSION = 2


@contextmanager
def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create the table if needed and migrate older databases in place."""
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                url          TEXT    UNIQUE NOT NULL,
                title        TEXT,
                company      TEXT,
                location     TEXT,
                track        TEXT,
                tier         TEXT,
                ai_verdict   TEXT,
                scraped_date TEXT,
                created_at   TEXT
            )
        """)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version < 2:
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(jobs)")}
            for name, ddl in (
                ("last_seen", "TEXT"),
                ("active", "INTEGER DEFAULT 1"),
                ("reason", "TEXT"),      # why a verdict was reached; NULL = legacy row
                ("updated_at", "TEXT"),
            ):
                if name not in cols:
                    conn.execute(f"ALTER TABLE jobs ADD COLUMN {name} {ddl}")
            conn.execute("UPDATE jobs SET last_seen = COALESCE(last_seen, scraped_date)")
            conn.execute("UPDATE jobs SET active = 1 WHERE active IS NULL")
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_track_date ON jobs(track, scraped_date)")


def get_job(url: str):
    """Return the stored row as a dict, or None."""
    with _conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE url = ?", (url,)).fetchone()
        return dict(row) if row else None


def is_seen(url: str) -> bool:
    """True if this URL has a current (non-legacy) verdict stored, YES or NO."""
    row = get_job(url)
    return row is not None and row.get("reason") is not None


def save_job(job: dict) -> str:
    """
    Insert or update a job. Returns 'new', 'changed' (title/location/verdict changed) or 'unchanged'.
    Expected keys: url, title, company, location, track, tier, ai_verdict, reason (optional)
    """
    today, now = str(date.today()), datetime.now().isoformat(timespec="seconds")
    with _conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE url = ?", (job["url"],)).fetchone()
        if row is None:
            conn.execute(
                """INSERT INTO jobs (url, title, company, location, track, tier, ai_verdict,
                                     scraped_date, created_at, last_seen, active, reason, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,1,?,?)""",
                (job["url"], job.get("title", ""), job.get("company", ""), job.get("location", ""),
                 job.get("track", "A"), job.get("tier", "other"), job.get("ai_verdict", "YES"),
                 today, now, today, job.get("reason", ""), now),
            )
            return "new"
        changed = any(
            job.get(k) is not None and job.get(k) != row[k]
            for k in ("title", "location", "tier", "ai_verdict")
        )
        conn.execute(
            """UPDATE jobs SET title=?, location=?, tier=?, ai_verdict=?, reason=?,
                               last_seen=?, active=1, updated_at=? WHERE url=?""",
            (job.get("title", row["title"]), job.get("location", row["location"]),
             job.get("tier", row["tier"]), job.get("ai_verdict", row["ai_verdict"]),
             job.get("reason", row["reason"] or ""), today,
             now if changed else row["updated_at"], job["url"]),
        )
        return "changed" if changed else "unchanged"


def touch_job(url: str):
    """Mark an already-known job as still listed today (and re-activate it)."""
    with _conn() as conn:
        conn.execute("UPDATE jobs SET last_seen = ?, active = 1 WHERE url = ?", (str(date.today()), url))


def mark_removed(track: str, company: str, live_urls) -> int:
    """
    After a SUCCESSFUL fetch of a company's board, deactivate stored jobs that are no
    longer listed. Never call this after a failed fetch. Returns number deactivated.
    """
    live = set(live_urls)
    with _conn() as conn:
        rows = conn.execute(
            "SELECT url FROM jobs WHERE track=? AND company=? AND active=1", (track, company)
        ).fetchall()
        gone = [r["url"] for r in rows if r["url"] not in live]
        for u in gone:
            conn.execute("UPDATE jobs SET active=0, updated_at=? WHERE url=?",
                         (datetime.now().isoformat(timespec="seconds"), u))
        return len(gone)


_TIER_ORDER = "CASE tier WHEN '1' THEN 1 WHEN '2' THEN 2 WHEN '3' THEN 3 ELSE 4 END"


def get_new_yes_jobs(track: str, since_days: int = 0) -> list:
    """Active YES jobs first seen within the last `since_days` days (0 = today only)."""
    cutoff = str(date.today() - timedelta(days=max(0, since_days)))
    with _conn() as conn:
        rows = conn.execute(
            f"""SELECT title, company, location, url, tier, scraped_date FROM jobs
                WHERE track=? AND ai_verdict='YES' AND active=1 AND scraped_date >= ?
                ORDER BY {_TIER_ORDER}, company, title""",
            (track, cutoff),
        ).fetchall()
    return [dict(r) for r in rows]


def get_todays_yes_jobs(track: str) -> list:
    return get_new_yes_jobs(track, 0)


def get_removed_since(since_days: int = 0) -> list:
    """Jobs deactivated recently (for the report's 'no longer listed' section)."""
    cutoff = str(date.today() - timedelta(days=max(0, since_days)))
    with _conn() as conn:
        rows = conn.execute(
            """SELECT title, company, url FROM jobs
               WHERE active=0 AND ai_verdict='YES' AND substr(updated_at,1,10) >= ?
               ORDER BY company, title""", (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def get_stats_today() -> dict:
    today = str(date.today())
    with _conn() as conn:
        def n(where, *args):
            return conn.execute(f"SELECT COUNT(*) FROM jobs WHERE {where}", args).fetchone()[0]
        return {
            "total": n("scraped_date=?", today),
            "yes": n("scraped_date=? AND ai_verdict='YES'", today),
            "ats": n("scraped_date=? AND ai_verdict='YES' AND track='A'", today),
            "bigtech": n("scraped_date=? AND ai_verdict='YES' AND track='B'", today),
        }
