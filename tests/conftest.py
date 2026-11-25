import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def load_fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def db(tmp_path, monkeypatch):
    import database
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "jobs.db"))
    database.init_db()
    return database


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def json(self):
        return self._payload

    def raise_for_status(self):
        import requests
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    """Offline stand-in for requests.Session: routes by URL substring."""
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def get(self, url, timeout=None, **kw):
        self.calls.append(url)
        for key, (payload, status) in self.routes.items():
            if key in url:
                return FakeResponse(payload, status)
        return FakeResponse(None, 404)


@pytest.fixture
def fake_session():
    return FakeSession({
        "boards/acme/jobs": (load_fixture("greenhouse_acme.json"), 200),
        "postings/beta": (load_fixture("lever_beta.json"), 200),
        "boards/broken": (None, 500),
    })


@pytest.fixture
def sample_config():
    return {
        "ai": {"enabled": False},
        "track_a": {"request_delay_seconds": 0,
                    "greenhouse_companies": [{"slug": "acme", "name": "Acme"}],
                    "lever_companies": [{"slug": "beta", "name": "Beta"}]},
        "limits": {"track_a_report_max": 25, "track_b_report_max": 30},
        "email": {"enabled": True, "recipient_email": "me@example.com", "smtp_host": "127.0.0.1"},
    }
