"""
main.py — Orchestrator for F-1 Job Hunter Agent

Usage:
  python3 main.py              # Full run (scrape + analyze + report + notify)
  python3 main.py --dry-run    # Test run — no DB writes, no AI calls, no notification
  python3 main.py --track a    # Run only Track A (ATS)
  python3 main.py --track b    # Run only Track B (BigTech)
  python3 main.py --report     # Only regenerate today's reports (skip scraping)
"""

import argparse
import concurrent.futures
import logging
import os
import sys
import time
import traceback
import yaml
from datetime import datetime

import database
import ai_analyzer
import scraper_ats
import scraper_bigtech
import report_generator
import notifier
import emailer

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")

def setup_logging():
    os.makedirs(LOGS_DIR, exist_ok=True)
    log_file = os.path.join(LOGS_DIR, f"run_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return log_file

# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

def preflight_checks(config: dict) -> bool:
    """Run sanity checks before starting the main scrape."""
    logger = logging.getLogger("preflight")
    all_ok = True

    # Check Ollama
    if not ai_analyzer.is_ollama_running():
        logger.error("❌ Ollama is not running! Start it with: ollama serve")
        logger.error("   Then pull the model: ollama pull llama3.2")
        all_ok = False
    else:
        model = config.get("ai", {}).get("model", "llama3.2")
        logger.info(f"✅ Ollama running — model: {model}")

    # Check config exists
    if not os.path.exists(CONFIG_PATH):
        logger.error(f"❌ config.yaml not found at: {CONFIG_PATH}")
        all_ok = False
    else:
        logger.info("✅ config.yaml loaded")

    return all_ok

# ---------------------------------------------------------------------------
# Main runners
# ---------------------------------------------------------------------------

def run_track_a(config: dict, dry_run: bool) -> int:
    logger = logging.getLogger("track_a")
    logger.info("=" * 60)
    logger.info("TRACK A — ATS / Aggregator Scraper")
    logger.info("=" * 60)
    try:
        return scraper_ats.run(config, dry_run=dry_run)
    except Exception as e:
        logger.error(f"Track A crashed: {e}")
        logger.debug(traceback.format_exc())
        return 0


def run_track_b(config: dict, dry_run: bool) -> int:
    logger = logging.getLogger("track_b")
    logger.info("=" * 60)
    logger.info("TRACK B — Big Tech Direct Career Pages Scraper")
    logger.info("=" * 60)
    try:
        return scraper_bigtech.run(config, dry_run=dry_run)
    except Exception as e:
        logger.error(f"Track B crashed: {e}")
        logger.debug(traceback.format_exc())
        return 0

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="F-1 Job Hunter Agent — daily automated job scraper for F-1 OPT holders"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test mode: scrape job titles but skip AI analysis and DB writes",
    )
    parser.add_argument(
        "--track",
        choices=["a", "b", "both"],
        default="both",
        help="Which track to run (default: both)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Skip scraping — only regenerate today's reports from existing DB data",
    )
    parser.add_argument(
        "--test-email",
        action="store_true",
        help="Send a test email to verify credentials (no scraping)",
    )
    args = parser.parse_args()

    log_file = setup_logging()
    logger = logging.getLogger("main")
    config = load_config()

    logger.info("=" * 60)
    logger.info("🏎️  F-1 JOB HUNTER AGENT — STARTING")
    logger.info(f"   Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"   Mode:     {'DRY RUN' if args.dry_run else 'LIVE'}")
    logger.info(f"   Track:    {args.track.upper()}")
    logger.info(f"   Log:      {log_file}")
    logger.info("=" * 60)

    # Initialize database
    database.init_db()

    # Pre-flight (skip in report-only mode or dry-run)
    if not args.report and not args.dry_run:
        if not preflight_checks(config):
            logger.error("Pre-flight checks failed. Aborting.")
            notifier.notify_error("Pre-flight checks failed. See logs.")
            sys.exit(1)

    # Test email mode — send sample email and exit
    if getattr(args, 'test_email', False):
        logger.info("Test email mode — sending sample digest...")
        ok = emailer.send_test_email(config)
        if ok:
            logger.info("✅ Test email sent! Check your inbox.")
        else:
            logger.error("❌ Test email failed — check .env credentials and config.yaml")
        return

    if args.report:
        # Only regenerate reports
        logger.info("Report-only mode — generating reports from DB...")
        ats_path, bt_path = report_generator.generate_all(config)
        logger.info(f"✅ ATS report:     {ats_path}")
        logger.info(f"✅ Big Tech report: {bt_path}")
        return

    start_time = time.time()
    ats_count = 0
    bigtech_count = 0

    if args.track in ("a", "both") and args.track in ("b", "both"):
        # Run both tracks in parallel using a thread pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(run_track_a, config, args.dry_run)
            future_b = executor.submit(run_track_b, config, args.dry_run)

            ats_count = future_a.result()
            bigtech_count = future_b.result()
    elif args.track == "a":
        ats_count = run_track_a(config, args.dry_run)
    elif args.track == "b":
        bigtech_count = run_track_b(config, args.dry_run)

    # Generate reports
    logger.info("Generating Markdown reports...")
    ats_path, bt_path = report_generator.generate_all(config)
    logger.info(f"✅ ATS report:      {ats_path}")
    logger.info(f"✅ Big Tech report:  {bt_path}")

    if not args.dry_run:
        # Pull today's YES jobs from DB for the email
        ats_jobs = database.get_todays_yes_jobs("A")
        bigtech_jobs = database.get_todays_yes_jobs("B")

        # Send email digest
        emailer.send_digest(
            ats_jobs=ats_jobs,
            bigtech_jobs=bigtech_jobs,
            ats_report_path=ats_path,
            bigtech_report_path=bt_path,
            config=config,
        )

        # macOS notification
        notifier.notify_run_complete(ats_count, bigtech_count, ats_path, bt_path)

    elapsed = round(time.time() - start_time, 1)
    logger.info("=" * 60)
    logger.info(f"🏁 DONE in {elapsed}s")
    logger.info(f"   ATS jobs (YES):     {ats_count}")
    logger.info(f"   Big Tech jobs (YES): {bigtech_count}")
    logger.info(f"   Total:              {ats_count + bigtech_count}")
    logger.info(f"   Reports in:         reports/")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
