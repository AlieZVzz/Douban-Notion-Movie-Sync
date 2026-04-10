#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

find_docker_bin() {
    if command -v docker >/dev/null 2>&1; then
        command -v docker
        return 0
    fi

    for candidate in /usr/local/bin/docker /usr/bin/docker; do
        if [ -x "$candidate" ]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done

    return 1
}

DOCKER_BIN=$(find_docker_bin || true)
if [ -z "$DOCKER_BIN" ]; then
    echo "docker 未安装，无法执行容器任务" >&2
    exit 1
fi

cd "$PROJECT_DIR"
mkdir -p "$PROJECT_DIR/posters" "$PROJECT_DIR/logs"

if [ ! -f "$PROJECT_DIR/src/config.yaml" ]; then
    echo "缺少 src/config.yaml，请先根据 config.example.yaml 填好配置" >&2
    exit 1
fi

if "$DOCKER_BIN" compose version >/dev/null 2>&1; then
    exec "$DOCKER_BIN" compose run --rm doubannotionsync
fi

if command -v docker-compose >/dev/null 2>&1; then
    exec docker-compose run --rm doubannotionsync
fi

echo "docker compose 未安装，无法执行容器任务" >&2
exit 1