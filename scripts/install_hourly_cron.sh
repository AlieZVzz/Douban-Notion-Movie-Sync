#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TMP_CRON=$(mktemp)
CRON_MARK="# doubannotionsync-hourly"
CRON_COMMAND="0 * * * * /bin/sh '$PROJECT_DIR/scripts/docker-run-once.sh' >> '$PROJECT_DIR/logs/cron.log' 2>&1 $CRON_MARK"

mkdir -p "$PROJECT_DIR/logs"

if crontab -l >/dev/null 2>&1; then
    crontab -l | grep -v "$CRON_MARK" > "$TMP_CRON"
else
    : > "$TMP_CRON"
fi

printf '%s\n' "$CRON_COMMAND" >> "$TMP_CRON"
crontab "$TMP_CRON"
rm -f "$TMP_CRON"

echo "已安装每小时任务：0 * * * *"
echo "日志文件：$PROJECT_DIR/logs/cron.log"