import subprocess
import sys

import pytest

import config_loader
import main as main_mod
import scraper_ats
import scraper_bigtech
from tests.conftest import ROOT


def test_help_runs_without_playwright_or_config_side_effects():
    out = subprocess.run([sys.executable, "main.py", "--help"], cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0
    for flag in ("--dry-run", "--track", "--limit", "--no-email", "--config", "--since"):
        assert flag in out.stdout


def test_missing_config_gives_clear_error(capsys):
    assert main_mod.main(["--config", "/nonexistent.yaml", "--dry-run"]) == 2
    assert "Config file not found" in capsys.readouterr().err


def test_bad_yaml(tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text("a: [unclosed")
    assert main_mod.main(["--config", str(bad)]) == 2


def test_example_config_loads_and_has_no_personal_data():
    cfg = config_loader.load_config(config_loader.EXAMPLE)
    assert cfg["email"]["recipient_email"] == "" and cfg["email"]["enabled"] is False
    assert cfg["track_a"]["greenhouse_companies"]


def test_dry_run_end_to_end_offline(monkeypatch, fake_session, tmp_path, capsys):
    import database
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "x.db"))
    cfg = tmp_path / "c.yaml"
    cfg.write_text("track_a:\n  request_delay_seconds: 0\n  greenhouse_companies:\n    - {slug: acme, name: Acme}\n")
    monkeypatch.setattr(scraper_ats, "make_session", lambda: fake_session)
    assert main_mod.main(["--dry-run", "--config", str(cfg)]) == 0
    out = capsys.readouterr().out
    assert "Total matches: 2" in out and "nothing was written" in out
    assert not (tmp_path / "x.db").exists()


def test_track_b_without_playwright_degrades(monkeypatch):
    monkeypatch.setattr(scraper_bigtech, "PLAYWRIGHT_OK", False)
    stats = scraper_bigtech.run({"track_b": {"companies": []}})
    assert stats["error"] == "playwright-missing" and stats["yes"] == 0


def test_robots_parsing(monkeypatch):
    class R:
        status_code = 200
        text = "User-agent: *\nDisallow: /private\n"
    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: R())
    scraper_bigtech._robots_cache.clear()
    assert scraper_bigtech.robots_allows("https://site.example/jobs")
    assert not scraper_bigtech.robots_allows("https://site.example/private/x")
