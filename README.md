# F-1 Job Hunter

A **personal** command-line tool that pulls public job postings, keeps the ones that look
usable for an F-1 OPT new grad, and writes a Markdown digest (optionally emailed to yourself).
It is a small personal project, not a service: it runs on your machine, uses only free tools,
and **all job data stays local** (SQLite file, reports and logs are git-ignored).

## What works today

| Part | Status |
|---|---|
| **Track A** - Greenhouse (and Lever) public JSON job-board APIs | Works. 46 of the 61 shipped Greenhouse boards answered on the last full run (~9,500 postings fetched in about 80 s); the 15 dead slugs were removed from the config. |
| Role matching, US/remote location filter, rule-based eligibility filter | Works, unit-tested (see Testing). |
| SQLite dedup, change and "no longer listed" tracking | Works, unit-tested; tested against a copy of a real legacy database. |
| Markdown reports, `--since`, email digest, macOS notification | Work (email is tested only against a local fake SMTP server). |
| **Track B** - Playwright on Big Tech career pages | **Best effort.** Last checked 2026-11-24: **Apple** (15 listings), **NVIDIA** (Workday, 20), **Adobe** (30) return listings; **OpenAI** (5) and **Netflix** (2) run through a generic link scraper and are low quality. **Meta, Amazon, Google, Salesforce** returned 0 listings and **Microsoft's** old domain no longer resolves, so those five are `enabled: false` in the config. Career sites change often, expect to maintain this track. |

How eligibility works: a posting is rejected (`NO`) only on an explicit red flag - "no / unable to
provide sponsorship", "US citizens only", security clearance (TS/SCI, polygraph, ...), or a stated
requirement of 3+ years of experience. Anything unclear is kept (`YES`), so **always read the full
posting**. Each decision stores a short reason (e.g. `rules:clearance (TS/SCI)`). An optional local
Ollama model can add vetoes (`ai.enabled: true`), but it is off by default: in an earlier version
the LLM rejected ~99% of postings, which is why the deterministic rules are the primary filter.

## Setup

```bash
git clone https://github.com/parvashah29/F1-Job-Hunter.git
cd F1-Job-Hunter
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml     # your personal copy (git-ignored)
```

Python 3.10+ (developed on 3.12, macOS arm64). Track B additionally needs
`playwright install chromium` (about 100 MB download); Track A does not.

Optional email: `cp .env.example .env`, fill in `SENDER_EMAIL` and a Gmail
[App Password](https://myaccount.google.com/apppasswords), then set `email.enabled: true` and
`email.recipient_email` in `config.yaml`. Without them the email step is skipped with a log line.

## Usage

```bash
python main.py --dry-run --limit 3          # 3 boards, prints matches, writes nothing
python main.py --track a --no-email         # real run, Track A only
python main.py --track both                 # also run the Playwright sites
python main.py --track b --site Apple --dry-run --limit 3
python main.py --report --since 3           # rebuild reports (jobs first seen in last 4 days)
python main.py --config my.yaml
```

Flags: `--dry-run` (no DB, report, email or LLM writes/calls), `--track a|b|both` (default `a`),
`--limit N`, `--since DAYS`, `--site NAME` (Track B), `--no-email`, `--no-notify`, `--config PATH`,
`--report`, `--test-email` (sends one real sample email to your recipient - only use it when you want that).

Config: `config.yaml` if it exists, otherwise `config.example.yaml`. Tiers and early-career keywords
under `roles:` drive title matching; add boards under `track_a`; disable a Track B site with
`enabled: false`.

Output: `reports/daily_jobs_YYYY-MM-DD.md`, `reports/bigtech_jobs_YYYY-MM-DD.md`, `logs/run_*.log`,
`data/jobs.db`. Reports list new jobs by tier, a run summary (boards that failed), and jobs that
disappeared from their board.

### Scheduling

`bash setup_cron.sh` only **prints** a cron line and (on macOS) a launchd plist. It installs
nothing unless you run `bash setup_cron.sh --install` interactively and confirm. On a laptop,
launchd is preferable because cron skips runs while the Mac sleeps.

## Behaviour and etiquette

- Track A uses documented public JSON endpoints, one request per company, ~1 s apart, with
  retries/backoff on 429/5xx, 20 s timeouts and a User-Agent that identifies this personal script.
- Track B checks `robots.txt`, uses the same identifying User-Agent, waits between pages, and does
  not try to evade bot protection: a site that blocks automation should be disabled, not bypassed.
- A failing board or site is logged and skipped; it never stops the run, and a failed fetch never
  marks jobs as removed.
- Secrets live only in `.env`; they are never logged. The DB schema is versioned and migrates old
  databases in place.
- Respect each site's terms of service. This is for personal job searching, not redistribution.

## Testing

```bash
pip install -r requirements-dev.txt
pytest
```

85 tests, fully offline: recorded-style Greenhouse/Lever fixtures, tricky locations ("Remote - US",
"Hybrid - New York", "Remote - Canada"), eligibility phrases ("No sponsorship", "US citizens only",
"TS/SCI"), DB migration/dedup/removal, report rendering, email MIME and HTML escaping, delivery
through a local `aiosmtpd` server, and the CLI. Track B scrapers are **not** unit-tested because
they need a live browser and the real sites.

## Limitations

- Eligibility is keyword-based; it cannot understand nuanced wording and defaults to keeping a job.
- Only boards on Greenhouse/Lever are covered reliably; location text varies by company.
- Track B selectors rot; Apple/NVIDIA/Adobe may break at any time.
- The LLM option has not been re-validated since the rules became the primary filter.

`F1_Job_Hunter_PRD.md` is the original product brief; the README above reflects the current code.
