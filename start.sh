#!/bin/bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR/edict"

case "${1:-up}" in
  up|start)
    docker compose up -d --build
    echo ""
    echo "Edict 已通过当前主栈启动："
    echo "  前端总控台: http://127.0.0.1:7899"
    echo "  后端健康检查: http://127.0.0.1:7898/health"
    ;;
  stop|down)
    docker compose down
    ;;
  restart)
    docker compose down
    docker compose up -d --build
    ;;
  status|ps)
    docker compose ps
    ;;
  logs)
    shift || true
    docker compose logs "$@"
    ;;
  *)
    echo "用法: $0 {start|stop|restart|status|logs}"
    echo "当前主启动入口: edict/docker-compose.yml"
    exit 1
    ;;
esac
