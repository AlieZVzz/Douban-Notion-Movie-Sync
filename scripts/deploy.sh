#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
INSTALL_CRON=${1:-}

cd "$PROJECT_DIR"
mkdir -p "$PROJECT_DIR/posters" "$PROJECT_DIR/logs"

if [ ! -f "$PROJECT_DIR/src/config.yaml" ]; then
    echo "缺少 src/config.yaml，请先根据 config.example.yaml 创建配置文件" >&2
    exit 1
fi

if docker compose version >/dev/null 2>&1; then
    docker compose build doubannotionsync
elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose build doubannotionsync
else
    echo "docker compose 未安装，无法构建镜像" >&2
    exit 1
fi

echo "镜像构建完成，可以先执行 ./scripts/docker-run-once.sh 验证一次运行。"

if [ "$INSTALL_CRON" = "--install-cron" ]; then
    "$PROJECT_DIR/scripts/install_hourly_cron.sh"
fi