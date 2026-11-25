"""notifier.py - optional macOS desktop notification via osascript; a silent no-op elsewhere."""

import logging
import subprocess
import sys

logger = logging.getLogger(__name__)


def _as_escape(text: str) -> str:
    """Escape for an AppleScript double-quoted string (prevents script injection from job data)."""
    return (text or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def send_notification(title: str, message: str, subtitle: str = "") -> bool:
    """Returns True if a notification was sent. No-op (False) when not on macOS."""
    if sys.platform != "darwin":
        logger.debug("[Notifier] not macOS - skipping notification")
        return False
    script = f'display notification "{_as_escape(message)}" with title "{_as_escape(title)}"'
    if subtitle:
        script += f' subtitle "{_as_escape(subtitle)}"'
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True, timeout=10)
        return True
    except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
        logger.warning(f"[Notifier] notification failed: {type(e).__name__}")
        return False


def notify_run_complete(ats_count: int, bigtech_count: int, *_ignored) -> bool:
    total = ats_count + bigtech_count
    return send_notification(
        "F-1 Job Hunter - run complete",
        f"{total} new jobs: {ats_count} ATS, {bigtech_count} Big Tech",
        "Open the reports/ folder",
    )


def notify_error(error_msg: str) -> bool:
    return send_notification("F-1 Job Hunter - error", error_msg[:100], "Check logs/")
