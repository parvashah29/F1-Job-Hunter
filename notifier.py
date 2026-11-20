"""
notifier.py — macOS desktop notification sender for F-1 Job Hunter Agent
Uses osascript (AppleScript) — no third-party libraries required.
"""

import subprocess
import logging

logger = logging.getLogger(__name__)


def send_notification(title: str, message: str, subtitle: str = ""):
    """
    Send a macOS desktop notification via osascript.
    Falls back to terminal print if osascript is unavailable.
    """
    try:
        subtitle_part = f'subtitle "{subtitle}"' if subtitle else ""
        script = (
            f'display notification "{message}" '
            f'with title "{title}" '
            f'{subtitle_part}'
        )
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
        logger.info(f"[Notifier] Sent: {title} — {message}")
    except subprocess.CalledProcessError as e:
        logger.warning(f"[Notifier] osascript failed: {e}")
        _fallback_print(title, message)
    except FileNotFoundError:
        logger.warning("[Notifier] osascript not found — not running on macOS?")
        _fallback_print(title, message)


def _fallback_print(title: str, message: str):
    print(f"\n{'=' * 50}")
    print(f"📢 {title}")
    print(f"   {message}")
    print(f"{'=' * 50}\n")


def notify_run_complete(ats_count: int, bigtech_count: int, ats_path: str, bigtech_path: str):
    """Send the end-of-run summary notification."""
    total = ats_count + bigtech_count
    title = "🔥 F-1 Job Hunter — Reports Ready!"
    message = f"{total} new jobs: {ats_count} from ATS, {bigtech_count} from Big Tech"
    subtitle = "Open reports/ folder to review"
    send_notification(title, message, subtitle)


def notify_error(error_msg: str):
    """Send an error notification."""
    send_notification(
        title="⚠️ F-1 Job Hunter — Error",
        message=error_msg[:100],
        subtitle="Check logs/ for details",
    )
