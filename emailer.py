"""
emailer.py — Email delivery for F-1 Job Hunter Agent

Converts both Markdown reports to a single, beautiful HTML email
and sends it via Gmail SMTP using a free App Password.

Credentials are loaded from .env — never hardcoded.
"""

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import date
from pathlib import Path

from html import escape as _e

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTML email template — clean, dark-accented design
# ---------------------------------------------------------------------------

EMAIL_HTML_WRAPPER = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>F-1 Job Digest</title>
<style>
  /* ── Reset ── */
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    background: #f0f4f8;
    color: #1a202c;
    line-height: 1.65;
  }}

  /* ── Outer wrapper ── */
  .email-wrapper {{
    max-width: 720px;
    margin: 32px auto;
    background: #ffffff;
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 4px 24px rgba(0,0,0,0.10);
  }}

  /* ── Header ── */
  .header {{
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    padding: 40px 40px 32px;
    text-align: center;
  }}
  .header h1 {{
    font-size: 26px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.5px;
    margin-bottom: 6px;
  }}
  .header .subtitle {{
    color: #90cdf4;
    font-size: 14px;
    font-weight: 400;
  }}

  /* ── Stats strip ── */
  .stats-strip {{
    background: #0f3460;
    padding: 16px 40px;
    display: flex;
    justify-content: center;
    gap: 40px;
    border-bottom: 1px solid #1a4a7a;
  }}
  .stat {{
    text-align: center;
  }}
  .stat .num {{
    display: block;
    font-size: 28px;
    font-weight: 800;
    color: #63b3ed;
    line-height: 1;
  }}
  .stat .label {{
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #90cdf4;
    margin-top: 4px;
  }}

  /* ── Body ── */
  .body {{
    padding: 36px 40px;
  }}

  /* ── Section headers ── */
  .section-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 32px 0 16px;
    padding-bottom: 10px;
    border-bottom: 2px solid #e2e8f0;
  }}
  .section-header h2 {{
    font-size: 18px;
    font-weight: 700;
    color: #1a202c;
  }}
  .section-badge {{
    background: #ebf8ff;
    color: #2b6cb0;
    font-size: 11px;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 20px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}

  /* ── Tier headers ── */
  .tier-header {{
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #718096;
    margin: 24px 0 12px;
    padding: 6px 0;
    border-bottom: 1px dashed #e2e8f0;
  }}

  /* ── Job card ── */
  .job-card {{
    background: #f7fafc;
    border: 1px solid #e2e8f0;
    border-left: 4px solid #4299e1;
    border-radius: 8px;
    padding: 16px 18px;
    margin-bottom: 12px;
    transition: all 0.2s;
  }}
  .job-card.tier1 {{ border-left-color: #48bb78; }}
  .job-card.tier2 {{ border-left-color: #4299e1; }}
  .job-card.tier3 {{ border-left-color: #ed8936; }}
  .job-card .job-title {{
    font-size: 15px;
    font-weight: 700;
    color: #1a202c;
    margin-bottom: 4px;
  }}
  .job-card .job-meta {{
    font-size: 13px;
    color: #718096;
    margin-bottom: 10px;
  }}
  .apply-btn {{
    display: inline-block;
    background: linear-gradient(135deg, #2b6cb0, #4299e1);
    color: #ffffff !important;
    text-decoration: none !important;
    font-size: 12px;
    font-weight: 700;
    padding: 6px 16px;
    border-radius: 6px;
    letter-spacing: 0.3px;
  }}
  .apply-btn:hover {{ opacity: 0.9; }}

  /* ── Company group (BigTech) ── */
  .company-group {{
    margin-bottom: 24px;
  }}
  .company-name {{
    font-size: 16px;
    font-weight: 800;
    color: #2d3748;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .company-count {{
    background: #edf2f7;
    color: #4a5568;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 10px;
  }}

  /* ── Empty state ── */
  .empty-state {{
    background: #fffaf0;
    border: 1px solid #feebc8;
    border-radius: 8px;
    padding: 20px;
    color: #744210;
    font-size: 14px;
    text-align: center;
  }}

  /* ── Footer ── */
  .footer {{
    background: #f7fafc;
    border-top: 1px solid #e2e8f0;
    padding: 24px 40px;
    text-align: center;
  }}
  .footer p {{
    font-size: 12px;
    color: #a0aec0;
    line-height: 1.8;
  }}
  .footer strong {{ color: #718096; }}
</style>
</head>
<body>
<div class="email-wrapper">

  <!-- Header -->
  <div class="header">
    <h1>🏎️ F-1 Job Hunter</h1>
    <p class="subtitle">Your daily curated job digest — {date}</p>
  </div>

  <!-- Stats strip -->
  <div class="stats-strip">
    <div class="stat">
      <span class="num">{total}</span>
      <span class="label">Total Jobs</span>
    </div>
    <div class="stat">
      <span class="num">{ats_count}</span>
      <span class="label">ATS / Startups</span>
    </div>
    <div class="stat">
      <span class="num">{bigtech_count}</span>
      <span class="label">Big Tech</span>
    </div>
  </div>

  <!-- Body -->
  <div class="body">
    {body_content}
  </div>

  <!-- Footer -->
  <div class="footer">
    <p>
      Generated by <strong>F-1 Job Hunter Agent</strong> · {date}<br>
      All jobs pre-filtered by AI (Ollama · llama3.2) for F-1 OPT sponsorship eligibility.<br>
      <strong>Always review the full job description before applying.</strong>
    </p>
  </div>

</div>
</body>
</html>"""

TIER_COLORS = {"1": "tier1", "2": "tier2", "3": "tier3"}
TIER_LABELS = {
    "1": "🥇 Tier 1 — Highest Priority",
    "2": "🥈 Tier 2 — Very Strong Match",
    "3": "🥉 Tier 3 — Good Opportunity",
    "other": "📌 Other",
}


# ---------------------------------------------------------------------------
# HTML builders
# ---------------------------------------------------------------------------

def _build_ats_html(jobs: list) -> str:
    """Build the Track A HTML section."""
    if not jobs:
        return """
        <div class="section-header">
            <h2>📋 ATS & Startups</h2>
            <span class="section-badge">Track A</span>
        </div>
        <div class="empty-state">No new ATS jobs found today matching your criteria.</div>
        """

    # Group by tier
    by_tier = {"1": [], "2": [], "3": [], "other": []}
    for j in jobs:
        by_tier.setdefault(j.get("tier", "other"), []).append(j)

    html = """
    <div class="section-header">
        <h2>📋 ATS &amp; Startups</h2>
        <span class="section-badge">Track A · {count} jobs</span>
    </div>
    """.format(count=len(jobs))

    for tier_key in ["1", "2", "3", "other"]:
        tier_jobs = by_tier.get(tier_key, [])
        if not tier_jobs:
            continue
        html += f'<div class="tier-header">{TIER_LABELS.get(tier_key, "Other")}</div>'
        for job in tier_jobs:
            color = TIER_COLORS.get(tier_key, "tier3")
            loc = f' · 📍 {_e(job["location"])}' if job.get("location") else ""
            html += f"""
            <div class="job-card {color}">
                <div class="job-title">{_e(job['title'])}</div>
                <div class="job-meta"><strong>{_e(job['company'])}</strong>{loc}</div>
                <a class="apply-btn" href="{_e(job['url'], quote=True)}" target="_blank">Apply Now →</a>
            </div>"""

    return html


def _build_bigtech_html(jobs: list) -> str:
    """Build the Track B HTML section, grouped by company."""
    if not jobs:
        return """
        <div class="section-header">
            <h2>🏢 Big Tech</h2>
            <span class="section-badge">Track B</span>
        </div>
        <div class="empty-state">No Big Tech jobs found today — anti-bot protections may have blocked scraping. Check again tomorrow.</div>
        """

    # Group by company
    by_company: dict = {}
    for j in jobs:
        by_company.setdefault(j["company"], []).append(j)

    html = """
    <div class="section-header">
        <h2>🏢 Big Tech</h2>
        <span class="section-badge">Track B · {count} jobs</span>
    </div>
    """.format(count=len(jobs))

    for company, company_jobs in sorted(by_company.items(), key=lambda x: -len(x[1])):
        html += f"""
        <div class="company-group">
            <div class="company-name">
                {_e(company)}
                <span class="company-count">{len(company_jobs)} jobs</span>
            </div>"""
        for job in sorted(company_jobs, key=lambda j: j.get("tier", "3")):
            tier_key = job.get("tier", "3")
            color = TIER_COLORS.get(tier_key, "tier3")
            loc = f' · 📍 {_e(job["location"])}' if job.get("location") else ""
            html += f"""
            <div class="job-card {color}">
                <div class="job-title">{_e(job['title'])}</div>
                <div class="job-meta">{loc}</div>
                <a class="apply-btn" href="{_e(job['url'], quote=True)}" target="_blank">Apply Now →</a>
            </div>"""
        html += "</div>"

    return html


# ---------------------------------------------------------------------------
# Main send function
# ---------------------------------------------------------------------------

def build_message(ats_jobs, bigtech_jobs, ats_report_path, bigtech_report_path,
                  email_cfg, sender_email, recipient):
    """Construct the MIME message (no network). Returns (msg, total)."""
    today = str(date.today())
    total = len(ats_jobs) + len(bigtech_jobs)
    subject_template = email_cfg.get(
        "subject_template",
        "F-1 Job Digest - {date} | {total} new jobs ({ats} ATS, {bigtech} BigTech)")
    try:
        subject = subject_template.format(date=today, total=total, ats=len(ats_jobs),
                                          bigtech=len(bigtech_jobs))
    except (KeyError, IndexError, ValueError):
        subject = f"F-1 Job Digest - {today} | {total} new jobs"
    subject = subject.replace("\r", " ").replace("\n", " ")

    body_sections = []
    if email_cfg.get("include_ats", True):
        body_sections.append(_build_ats_html(ats_jobs))
    if email_cfg.get("include_bigtech", True):
        body_sections.append(_build_bigtech_html(bigtech_jobs))
    html_body = EMAIL_HTML_WRAPPER.format(
        date=today, total=total, ats_count=len(ats_jobs),
        bigtech_count=len(bigtech_jobs), body_content="\n".join(body_sections))

    def lines(jobs):
        return "\n".join(f"* {j['title']} @ {j['company']} - {j['url']}" for j in jobs[:25]) or "(none)"
    plain_text = (f"F-1 Job Digest - {today}\n"
                  f"Total: {total} jobs ({len(ats_jobs)} ATS, {len(bigtech_jobs)} BigTech)\n\n"
                  f"--- ATS jobs ---\n{lines(ats_jobs)}\n\n--- Big Tech jobs ---\n{lines(bigtech_jobs)}\n")

    msg = MIMEMultipart("mixed")
    msg["From"] = f"F-1 Job Hunter <{sender_email}>"
    msg["To"] = recipient
    msg["Subject"] = subject
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(plain_text, "plain", "utf-8"))
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    if email_cfg.get("include_attachments", True):
        for path, filename in [(ats_report_path, f"daily_jobs_{today}.md"),
                               (bigtech_report_path, f"bigtech_jobs_{today}.md")]:
            if path and os.path.exists(path):
                with open(path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
                msg.attach(part)
    return msg, total


def send_digest(ats_jobs: list, bigtech_jobs: list, ats_report_path: str,
                bigtech_report_path: str, config: dict) -> bool:
    """
    Build and send the digest via SMTP (Gmail by default). Returns True on success.
    Never raises; missing credentials/recipient/disabled config just log and return False.
    """
    email_cfg = config.get("email", {}) or {}
    if not email_cfg.get("enabled", False):
        logger.info("[Email] disabled in config (email.enabled: false) - skipping")
        return False

    load_dotenv(os.path.join(BASE_DIR, ".env"))
    sender_email = os.getenv("SENDER_EMAIL", "").strip()
    app_password = os.getenv("GMAIL_APP_PASSWORD", "").strip()
    recipient = (email_cfg.get("recipient_email") or "").strip()

    if not sender_email or not app_password:
        logger.warning("[Email] SENDER_EMAIL / GMAIL_APP_PASSWORD missing in .env - skipping email "
                       "(cp .env.example .env and fill it in)")
        return False
    if not recipient:
        logger.warning("[Email] email.recipient_email is empty in config - skipping email")
        return False

    msg, total = build_message(ats_jobs, bigtech_jobs, ats_report_path, bigtech_report_path,
                               email_cfg, sender_email, recipient)
    host = email_cfg.get("smtp_host", "smtp.gmail.com")
    port = int(email_cfg.get("smtp_port", 587))
    try:
        logger.info(f"[Email] Connecting to {host}:{port}...")
        if port == 465:
            server_cm = smtplib.SMTP_SSL(host, port, timeout=30)
        else:
            server_cm = smtplib.SMTP(host, port, timeout=30)
        with server_cm as server:
            if port != 465 and email_cfg.get("starttls", True):
                server.ehlo()
                server.starttls()
                server.ehlo()
            if email_cfg.get("auth", True):
                server.login(sender_email, app_password)
            server.sendmail(sender_email, [recipient], msg.as_string())
        logger.info(f"[Email] Digest sent - {total} jobs")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("[Email] SMTP authentication failed. Check the App Password in .env")
        return False
    except (smtplib.SMTPException, OSError) as e:
        logger.error(f"[Email] SMTP error: {type(e).__name__}: {e}")
        return False


def send_test_email(config: dict) -> bool:
    """Send a test email to verify credentials work before a real run."""
    return send_digest(
        ats_jobs=[{
            "title": "Data Scientist (Test Job)",
            "company": "Test Company Inc.",
            "location": "Remote, United States",
            "url": "https://example.com/apply",
            "tier": "1",
        }],
        bigtech_jobs=[{
            "title": "ML Engineer, University Graduate (Test)",
            "company": "Google",
            "location": "Mountain View, CA",
            "url": "https://careers.google.com",
            "tier": "1",
        }],
        ats_report_path="",
        bigtech_report_path="",
        config=config,
    )
