# syntax=docker/dockerfile:1

FROM busybox:1.36

CMD ["sh", "-c", "echo '根目录 Dockerfile 是旧版 7891 demo 入口，已废弃。请使用：cd edict && docker compose up -d --build'; exit 1"]
