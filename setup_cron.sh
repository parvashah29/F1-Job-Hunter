#!/usr/bin/env bash
# setup_cron.sh - SAFE scheduler helper for F-1 Job Hunter.
#
# By default this only PRINTS the cron line and a launchd alternative. It installs
# nothing unless you run it interactively with --install AND answer "y" to the prompt.
#
#   bash setup_cron.sh             # print the entries (no changes)
#   bash setup_cron.sh --install   # ask before adding the cron entry
#
# Options via env: HOUR (default 19), MINUTE (default 0)

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -x "$PROJECT_DIR/venv/bin/python" ]]; then
  PYTHON_BIN="$PROJECT_DIR/venv/bin/python"
else
  PYTHON_BIN="$(command -v python3 || true)"
fi
HOUR="${HOUR:-19}"
MINUTE="${MINUTE:-0}"
LOG_FILE="$PROJECT_DIR/logs/cron.log"
MARK="# F1-Job-Hunter"

if [[ -z "$PYTHON_BIN" ]]; then
  echo "python3 not found. Create the venv first: python3 -m venv venv && venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

CRON_LINE="$MINUTE $HOUR * * * cd \"$PROJECT_DIR\" && \"$PYTHON_BIN\" main.py >> \"$LOG_FILE\" 2>&1 $MARK"

echo "Project: $PROJECT_DIR"
echo "Python:  $PYTHON_BIN"
echo "Time:    daily at $(printf '%02d:%02d' "$HOUR" "$MINUTE") (local time)"
echo
echo "cron entry:"
echo "  $CRON_LINE"
echo
if [[ "$(uname)" == "Darwin" ]]; then
  echo "macOS note: cron works, but the Mac must be awake at that time. launchd is the"
  echo "native alternative: it runs a missed job after wake. Minimal plist for"
  echo "~/Library/LaunchAgents/com.f1jobhunter.plist (then: launchctl load <that file>):"
  cat <<PLIST

<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.f1jobhunter</string>
  <key>ProgramArguments</key><array>
    <string>$PYTHON_BIN</string><string>$PROJECT_DIR/main.py</string></array>
  <key>WorkingDirectory</key><string>$PROJECT_DIR</string>
  <key>StartCalendarInterval</key><dict>
    <key>Hour</key><integer>$HOUR</integer><key>Minute</key><integer>$MINUTE</integer></dict>
  <key>StandardOutPath</key><string>$LOG_FILE</string>
  <key>StandardErrorPath</key><string>$LOG_FILE</string>
</dict></plist>
PLIST
  echo
fi

if [[ "${1:-}" != "--install" ]]; then
  echo "Nothing was installed. Re-run with --install to add the cron entry (you will be asked first)."
  exit 0
fi

if [[ ! -t 0 ]]; then
  echo "Refusing to install from a non-interactive shell." >&2
  exit 1
fi

read -r -p "Add this entry to your crontab? [y/N] " CONFIRM
if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
  echo "Aborted; crontab unchanged."
  exit 0
fi

mkdir -p "$PROJECT_DIR/logs"
EXISTING="$(crontab -l 2>/dev/null || true)"
# Replace only our own previous entries (marker, legacy comment, or this project's main.py).
KEPT="$(printf '%s\n' "$EXISTING" | grep -v -F -e "$MARK" -e "F1 Job Hunter" -e "$PROJECT_DIR/main.py" || true)"
printf '%s\n%s\n' "$KEPT" "$CRON_LINE" | sed '/^$/N;/^\n$/D' | crontab -
echo "Installed. Verify with: crontab -l   Remove by deleting the line marked '$MARK' via: crontab -e"
