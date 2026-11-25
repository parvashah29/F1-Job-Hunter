"""
main.py - orchestrator for F-1 Job Hunter.

  python main.py --dry-run --limit 3      # fetch 3 boards, print matches, write nothing
  python main.py --track a                # Track A only (no browser needed)
  python main.py --no-email               # full run, skip the email digest
  python main.py --report --since 3       # rebuild reports from the DB (last 4 days)
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime

from config_loader import ConfigError, load_config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(BASE_DIR, "logs")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="main.py",
        description="F-1 Job Hunter - personal job scraper for F-1 OPT job searches "
                    "(Greenhouse/Lever APIs + best-effort Big Tech career pages).",
    )
    p.add_argument("--dry-run", action="store_true",
                   help="fetch and score jobs but write NOTHING: no DB, reports, email or LLM calls")
    p.add_argument("--track", choices=["a", "b", "both"], default="a",
                   help="a = Greenhouse/Lever APIs (default), b = Playwright Big Tech sites, both")
    p.add_argument("--limit", type=int, metavar="N",
                   help="smoke-test cap: Track A scrapes only the first N boards; "
                        "Track B processes at most N jobs per site")
    p.add_argument("--since", type=int, default=0, metavar="DAYS",
                   help="reports/email include jobs first seen in the last DAYS days (default 0 = today)")
    p.add_argument("--site", action="append", metavar="NAME",
                   help="Track B only: restrict to this site (repeatable), e.g. --site Apple")
    p.add_argument("--no-email", action="store_true", help="never send the email digest")
    p.add_argument("--no-notify", action="store_true", help="skip the macOS notification")
    p.add_argument("--config", metavar="PATH",
                   help="config file (default: config.yaml if present, else config.example.yaml)")
    p.add_argument("--report", action="store_true",
                   help="skip scraping; regenerate reports from the existing DB")
    p.add_argument("--test-email", action="store_true",
                   help="send a sample digest to the configured recipient and exit")
    return p


def setup_logging(to_file: bool) -> str:
    handlers = [logging.StreamHandler(sys.stdout)]
    log_file = ""
    if to_file:
        os.makedirs(LOGS_DIR, exist_ok=True)
        log_file = os.path.join(LOGS_DIR, f"run_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.log")
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
    return log_file


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    try:
        config = load_config(args.config)
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    log_file = setup_logging(to_file=not args.dry_run)
    log = logging.getLogger("main")

    import ai_analyzer
    import database
    import emailer
    import notifier
    import report_generator
    import role_matcher
    import scraper_ats

    role_matcher.configure(config)
    log.info(f"F-1 Job Hunter - {'DRY RUN' if args.dry_run else 'LIVE'} | track={args.track} "
             f"| config={os.path.basename(config['_path'])}")
    if log_file:
        log.info(f"log file: {log_file}")

    ai_cfg = config.get("ai", {}) or {}
    if ai_cfg.get("enabled") and not args.dry_run and not ai_analyzer.is_ollama_running(
            ai_cfg.get("ollama_url", ai_analyzer.DEFAULT_OLLAMA_URL)):
        log.warning("ai.enabled is true but Ollama is not reachable - using keyword rules only "
                    "(start it with `ollama serve`)")

    if args.test_email:
        ok = emailer.send_test_email(config)
        return 0 if ok else 1

    if not args.dry_run:
        database.init_db()

    if args.report:
        ats_path, bt_path = report_generator.generate_all(config, args.since)
        log.info(f"reports: {ats_path}, {bt_path}")
        return 0

    start = time.time()
    ats = {"yes": 0, "found": []}
    bt = {"yes": 0, "found": [], "results": {}}

    if args.track in ("a", "both"):
        try:
            ats = scraper_ats.run(config, dry_run=args.dry_run, limit=args.limit)
        except Exception as e:
            log.error(f"Track A crashed: {type(e).__name__}: {e}")
    if args.track in ("b", "both"):
        try:
            import scraper_bigtech
            bt = scraper_bigtech.run(config, dry_run=args.dry_run, limit=args.limit, only=args.site)
        except Exception as e:
            log.error(f"Track B crashed: {type(e).__name__}: {e}")

    if args.dry_run:
        print("\nDRY RUN - matches (nothing was written):")
        for j in ats.get("found", []) + bt.get("found", []):
            print(f"  [T{j['tier']}] {j['title']} @ {j['company']} - {j['location']}\n        {j['url']}")
        print(f"\nTotal matches: {len(ats.get('found', [])) + len(bt.get('found', []))}")
        return 0

    ats_path, bt_path = report_generator.generate_all(config, args.since, ats, bt)

    if args.no_email:
        log.info("email skipped (--no-email)")
    else:
        emailer.send_digest(
            ats_jobs=database.get_new_yes_jobs("A", args.since),
            bigtech_jobs=database.get_new_yes_jobs("B", args.since),
            ats_report_path=ats_path, bigtech_report_path=bt_path, config=config)

    if not args.no_notify:
        notifier.notify_run_complete(ats.get("yes", 0), bt.get("yes", 0))

    log.info(f"DONE in {time.time() - start:.1f}s - new YES: Track A {ats.get('yes', 0)}, "
             f"Track B {bt.get('yes', 0)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
