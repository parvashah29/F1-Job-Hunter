import email
import os
from email import policy

import pytest
from aiosmtpd.controller import Controller

import emailer
import notifier
import report_generator as rg

ATS = [{"title": "Data Scientist <script>alert(1)</script>", "company": "Acme & Co", "location": "Remote - US",
        "url": "https://example.com/a?x=1&y=2", "tier": "1"}]
BT = [{"title": "SWE, New Grad", "company": "Apple", "location": "Cupertino, CA",
       "url": "https://example.com/b", "tier": "1"}]


class Capture:
    def __init__(self):
        self.messages = []

    async def handle_DATA(self, server, session, envelope):
        self.messages.append(envelope)
        return "250 OK"


@pytest.fixture
def smtp_server():
    import socket
    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        port = sk.getsockname()[1]
    handler = Capture()
    ctl = Controller(handler, hostname="127.0.0.1", port=port)
    ctl.start()
    yield handler, port
    ctl.stop()


def test_build_message_structure_and_escaping(tmp_path):
    report = tmp_path / "r.md"
    report.write_text("# hi")
    msg, total = emailer.build_message(ATS, BT, str(report), "", {"include_attachments": True},
                                       "sender@example.com", "me@example.com")
    assert total == 2
    parsed = email.message_from_bytes(msg.as_bytes(), policy=policy.default)
    assert parsed["To"] == "me@example.com" and "2 new jobs" in parsed["Subject"]
    html = parsed.get_body(preferencelist=("html",)).get_content()
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "Acme &amp; Co" in html and "x=1&amp;y=2" in html
    plain = parsed.get_body(preferencelist=("plain",)).get_content()
    assert "SWE, New Grad @ Apple" in plain
    assert [p.get_filename() for p in parsed.iter_attachments()][0].startswith("daily_jobs_")


def test_subject_template_errors_and_header_injection():
    msg, _ = emailer.build_message([], [], "", "", {"subject_template": "Hi {nope}"}, "a@b.c", "d@e.f")
    assert msg["Subject"].startswith("F-1 Job Digest")


def test_send_digest_to_local_fake_smtp(monkeypatch, smtp_server, sample_config):
    handler, port = smtp_server
    monkeypatch.setenv("SENDER_EMAIL", "sender@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "not-a-real-password")
    monkeypatch.setattr(emailer, "load_dotenv", lambda *a, **k: None)
    sample_config["email"].update(smtp_port=port, starttls=False, auth=False)
    assert emailer.send_digest(ATS, BT, "", "", sample_config) is True
    assert len(handler.messages) == 1
    assert handler.messages[0].rcpt_tos == ["me@example.com"]
    got = email.message_from_bytes(handler.messages[0].content, policy=policy.default)
    assert "Data Scientist" in got.get_body(preferencelist=("plain",)).get_content()


def test_email_skips_without_credentials_or_when_disabled(monkeypatch, sample_config):
    monkeypatch.setattr(emailer, "load_dotenv", lambda *a, **k: None)
    monkeypatch.delenv("SENDER_EMAIL", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    assert emailer.send_digest(ATS, BT, "", "", sample_config) is False
    sample_config["email"]["enabled"] = False
    assert emailer.send_digest(ATS, BT, "", "", sample_config) is False


def test_email_connection_failure_returns_false(monkeypatch, sample_config):
    monkeypatch.setenv("SENDER_EMAIL", "s@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "x")
    monkeypatch.setattr(emailer, "load_dotenv", lambda *a, **k: None)
    sample_config["email"].update(smtp_port=1, starttls=False, auth=False)
    assert emailer.send_digest(ATS, BT, "", "", sample_config) is False


def test_reports_render_and_write(db, tmp_path, monkeypatch, sample_config):
    monkeypatch.setattr(rg, "REPORTS_DIR", str(tmp_path))
    db.save_job({"url": "https://x/1", "title": "Data [Scientist]", "company": "Acme", "location": "NYC",
                 "track": "A", "tier": "1", "ai_verdict": "YES", "reason": "rules:ok"})
    db.save_job({"url": "https://x/2", "title": "Gone", "company": "Acme", "location": "NYC",
                 "track": "A", "tier": "2", "ai_verdict": "YES", "reason": "rules:ok"})
    db.mark_removed("A", "Acme", ["https://x/1"])
    ats, bt = rg.generate_all(sample_config, 0, {"companies_ok": 1, "companies_failed": ["Ghost"]},
                              {"results": {"Meta": "disabled in config"}})
    text = open(ats).read()
    assert "Tier 1" in text and "Data \\[Scientist\\]" in text
    assert "Failed boards: Ghost" in text and "No longer listed (1)" in text
    assert "Meta: disabled in config" in open(bt).read()
    assert os.path.basename(ats).startswith("daily_jobs_")


def test_empty_report():
    assert "No new matching jobs" in rg.render_ats_report([])


def test_notifier_noop_off_mac(monkeypatch):
    monkeypatch.setattr(notifier.sys, "platform", "linux")
    assert notifier.send_notification("t", "m") is False


def test_notifier_escapes_applescript(monkeypatch):
    calls = []
    monkeypatch.setattr(notifier.sys, "platform", "darwin")
    monkeypatch.setattr(notifier.subprocess, "run", lambda cmd, **k: calls.append(cmd))
    notifier.send_notification('a"b', 'x" & do shell script "evil')
    script = calls[0][2]
    assert '\\"' in script and 'x" &' not in script
