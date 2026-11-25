import sqlite3


def job(url="https://x/1", **kw):
    d = dict(url=url, title="Data Scientist", company="Acme", location="Remote - US",
             track="A", tier="1", ai_verdict="YES", reason="rules:ok")
    d.update(kw)
    return d


def test_insert_dedup_and_change(db):
    assert db.save_job(job()) == "new"
    assert db.save_job(job()) == "unchanged"
    assert db.save_job(job(title="Data Scientist II")) == "changed"
    assert db.get_job("https://x/1")["title"] == "Data Scientist II"
    assert len(db.get_todays_yes_jobs("A")) == 1


def test_mark_removed_and_reactivate(db):
    db.save_job(job("https://x/1"))
    db.save_job(job("https://x/2"))
    assert db.mark_removed("A", "Acme", ["https://x/1"]) == 1
    assert [j["url"] for j in db.get_todays_yes_jobs("A")] == ["https://x/1"]
    assert [r["url"] for r in db.get_removed_since(0)] == ["https://x/2"]
    db.touch_job("https://x/2")
    assert len(db.get_todays_yes_jobs("A")) == 2


def test_no_verdict_rows_are_remembered(db):
    db.save_job(job(ai_verdict="NO", reason="rules:clearance"))
    assert db.is_seen("https://x/1")
    assert db.get_todays_yes_jobs("A") == []


def test_migrates_legacy_schema(tmp_path, monkeypatch):
    import database
    path = str(tmp_path / "old.db")
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT UNIQUE NOT NULL,
        title TEXT, company TEXT, location TEXT, track TEXT, tier TEXT, ai_verdict TEXT,
        scraped_date TEXT, created_at TEXT)""")
    conn.execute("INSERT INTO jobs (url,title,company,location,track,tier,ai_verdict,scraped_date,created_at)"
                 " VALUES ('https://old/1','T','C','L','A','1','NO','2026-07-21','x')")
    conn.commit(); conn.close()
    monkeypatch.setattr(database, "DB_PATH", path)
    database.init_db()
    database.init_db()  # idempotent
    row = database.get_job("https://old/1")
    assert row["active"] == 1 and row["reason"] is None
    assert not database.is_seen("https://old/1")  # legacy LLM verdicts are re-evaluated
    assert sqlite3.connect(path).execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
