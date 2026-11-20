#!/usr/bin/env bash
# setup_cron.sh — One-shot script to install the 7:00 PM daily cron job
# Run once: bash setup_cron.sh

set -e

# Resolve the absolute path to this project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$(which python3)"
MAIN_SCRIPT="$PROJECT_DIR/main.py"
LOG_FILE="$PROJECT_DIR/logs/cron.log"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🏎️  F-1 Job Hunter — Cron Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Project:  $PROJECT_DIR"
echo "Python:   $PYTHON_BIN"
echo "Schedule: Daily at 7:00 PM"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Ensure logs directory exists
mkdir -p "$PROJECT_DIR/logs"

# Build the cron line
# Format: minute hour * * * command
CRON_LINE="0 19 * * * cd \"$PROJECT_DIR\" && $PYTHON_BIN \"$MAIN_SCRIPT\" >> \"$LOG_FILE\" 2>&1"

# Check if cron is already installed
EXISTING_CRON=$(crontab -l 2>/dev/null || echo "")

if echo "$EXISTING_CRON" | grep -q "F1 Job Hunter\|f1_job_hunter\|main.py"; then
    echo ""
    echo "⚠️  A cron job for F-1 Job Hunter already exists:"
    crontab -l | grep "main.py"
    echo ""
    read -p "Replace it? (y/n): " CONFIRM
    if [[ "$CONFIRM" != "y" ]]; then
        echo "Aborted."
        exit 0
    fi
    # Remove existing entry
    NEW_CRON=$(echo "$EXISTING_CRON" | grep -v "main.py" | grep -v "F1 Job Hunter")
    EXISTING_CRON="$NEW_CRON"
fi

# Append new cron line
NEW_CRONTAB=$(printf "%s\n# F1 Job Hunter — runs at 7:00 PM daily\n%s\n" "$EXISTING_CRON" "$CRON_LINE")

# Install
echo "$NEW_CRONTAB" | crontab -

echo ""
echo "✅ Cron job installed! Your daily digest will run at 7:00 PM."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Verify with:  crontab -l"
echo "Remove with:  crontab -e  (then delete the line)"
echo "Logs at:      $LOG_FILE"
echo "Reports at:   $PROJECT_DIR/reports/"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
