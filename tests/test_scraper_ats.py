import scraper_ats
from tests.conftest import FakeSession


def test_html_to_text():
    assert scraper_ats.html_to_text("&lt;p&gt;Hello&lt;br&gt;&amp;amp; world&lt;/p&gt;").split() == ["Hello", "&", "world"]


def test_run_filters_and_dedups(db, fake_session, sample_config):
    stats = scraper_ats.run(sample_config, session=fake_session)
    titles = sorted(j["title"] for j in stats["found"])
    # accepted: Data Scientist (Remote-US), Analytics Engineer (no loc, "no clearance required"),
    # Python Developer (Remote - US). Rejected: senior, sponsorship, london, TS/SCI, 5+ yrs, citizen, Canada, non-role
    assert titles == ["Analytics Engineer", "Data Scientist, Growth", "Python Developer"]
    assert stats["no"] == 4 and stats["yes"] == 3
    assert stats["companies_ok"] == 2 and stats["fetched"] == 11

    again = scraper_ats.run(sample_config, session=fake_session)  # second run: nothing new
    assert again["processed"] == 0 and again["seen"] == 7 and again["yes"] == 0
    assert len(db.get_new_yes_jobs("A", 0)) == 3  # still reportable today


def test_removed_jobs_detected(db, sample_config):
    from tests.conftest import load_fixture
    full = FakeSession({"boards/acme/jobs": (load_fixture("greenhouse_acme.json"), 200)})
    sample_config["track_a"]["lever_companies"] = []
    scraper_ats.run(sample_config, session=full)
    shrunk = load_fixture("greenhouse_acme.json")
    shrunk["jobs"] = [j for j in shrunk["jobs"] if j["id"] != 1]
    stats = scraper_ats.run(sample_config, session=FakeSession({"boards/acme/jobs": (shrunk, 200)}))
    assert stats["removed"] == 1
    assert "Data Scientist, Growth" not in [j["title"] for j in db.get_new_yes_jobs("A", 0)]


def test_failed_board_is_isolated_and_does_not_remove_jobs(db, fake_session, sample_config):
    scraper_ats.run(sample_config, session=fake_session)
    sample_config["track_a"]["greenhouse_companies"] = [
        {"slug": "broken", "name": "Acme"}, {"slug": "missing", "name": "Ghost"}]
    stats = scraper_ats.run(sample_config, session=fake_session)
    assert stats["companies_failed"] == ["Acme", "Ghost"]
    assert stats["removed"] == 0
    assert stats["companies_ok"] == 1  # Lever still processed


def test_dry_run_writes_nothing(tmp_path, fake_session, sample_config, monkeypatch):
    import database
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "never.db"))
    stats = scraper_ats.run(sample_config, dry_run=True, session=fake_session)
    assert stats["yes"] == 3
    assert not (tmp_path / "never.db").exists()


def test_limit_caps_boards(db, fake_session, sample_config):
    stats = scraper_ats.run(sample_config, session=fake_session, limit=1)
    assert stats["companies_ok"] == 1
    assert len(fake_session.calls) == 1


def test_lever_requirements_list_is_scanned(db, fake_session, sample_config):
    stats = scraper_ats.run(sample_config, session=fake_session)
    assert "Applied AI Engineer" not in [j["title"] for j in stats["found"]]  # U.S. citizen in lists
