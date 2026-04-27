# 三省六部 Windows 安装说明

> 本文曾用于早期 OpenClaw + `dashboard/server.py` + `7891` 旧看板部署。旧部署路径已废弃，避免继续按旧文档启动 `run_loop.sh` 或 `python dashboard/server.py`。

## 当前推荐方式

Windows 用户请优先使用 Docker Desktop + 当前主栈：

```powershell
cd edict
copy .env.example .env
```

按需编辑 `.env`。如果使用 AstrBot：

```env
DISPATCH_BACKEND=astrbot
ASTRBOT_API_URL=http://host.docker.internal:6185
ASTRBOT_API_KEY=你的 AstrBot API Key
```

启动：

```powershell
docker compose up -d --build
```

访问：

```text
前端总控台：http://127.0.0.1:7899
后端健康检查：http://127.0.0.1:7898/health
后端 API：http://127.0.0.1:7898/api/live-status
```

## 常用排查

```powershell
docker compose ps
docker compose logs backend --tail=100
docker compose logs dispatcher --tail=100
```

## 旧部署迁移提示

如果你以前按旧版 OpenClaw workspace 方式安装过，可能残留这些内容：

- `workspace-*/data`
- `workspace-*/scripts`
- 旧的 `dashboard/server.py` 进程
- 旧的 `run_loop.sh` 后台进程

迁移到当前 Docker Compose 主栈前，先停止旧进程，确认浏览器打开的是 `7899`，不是旧的 `7891`。

更多说明见：

- `README.md`
- `docs/getting-started.md`
- `edict/docs/astrbot-integration-guide.md`
