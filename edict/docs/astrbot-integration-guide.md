# Edict 对接 AstrBot 指导手册

> 本文档面向 Windows Docker Desktop 用户，指导如何启动 Edict 项目并对接本地 AstrBot。

---

## 目录

1. [前置条件](#1-前置条件)
2. [获取 AstrBot API Key](#2-获取-astrbot-api-key)
3. [配置 Edict 对接 AstrBot](#3-配置-edict-对接-astrbot)
4. [启动项目](#4-启动项目)
5. [验证对接是否成功](#5-验证对接是否成功)
6. [常见问题](#6-常见问题)

---

## 1. 前置条件

| 条件 | 说明 |
|------|------|
| Windows 10/11 | 安装 Docker Desktop |
| Docker Desktop | 已启动并运行 |
| AstrBot | 本地已部署并运行在 `http://localhost:6185` |

确认 AstrBot 正在运行：

```bash
curl http://localhost:6185/api/v1/chat -X POST -H "Content-Type: application/json" -d "{\"username\":\"test\",\"message\":\"hello\"}"
```

如果返回 JSON 或 SSE 流，说明 AstrBot 正常运行。

---

## 2. 获取 AstrBot API Key

AstrBot 使用 API Key 进行鉴权，格式为 `abk_xxx`。获取步骤如下：

### 2.1 打开 AstrBot 管理面板

浏览器访问：**http://localhost:6185**

### 2.2 进入设置页面

登录后，点击左侧导航栏 **设置**（Settings）。

### 2.3 创建 API Key

1. 在设置页面找到 **API Key** 或 **API 密钥** 区域
2. 点击 **创建新密钥**（Create New Key）
3. **权限范围（Scope）** 必须勾选 **`chat`**（聊天接口权限）
4. 点击确认创建
5. 复制生成的 API Key（格式类似 `abk_a1b2c3d4e5f6...`）

> ⚠️ **重要**：API Key 只在创建时显示一次，请立即保存。如果丢失需要重新创建。

---

## 3. 配置 Edict 对接 AstrBot

### 3.1 修改 docker-compose.yml

打开 `edict/docker-compose.yml`，找到 `dispatcher` 服务的 `environment` 部分，修改如下：

```yaml
  dispatcher:
    build:
      context: ..
      dockerfile: edict/Dockerfile
    environment:
      DATABASE_URL: postgresql+asyncpg://edict:edict_dev_2024@postgres:5432/edict
      REDIS_URL: redis://redis:6379/0
      OPENCLAW_PROJECT_DIR: /app
      # ── 切换为 AstrBot 后端 ──
      DISPATCH_BACKEND: astrbot
      # ── AstrBot 配置 ──
      ASTRBOT_API_URL: http://host.docker.internal:6185
      ASTRBOT_API_KEY: abk_你的密钥粘贴到这里
      ASTRBOT_TIMEOUT_SEC: 300
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ../agents:/app/agents:ro
      - ../scripts:/app/scripts
      - ../data:/app/data
    command: python -m app.workers.dispatch_worker
    restart: unless-stopped
```

**关键配置说明：**

| 环境变量 | 值 | 说明 |
|----------|---|------|
| `DISPATCH_BACKEND` | `astrbot` | 选择 AstrBot 作为 Agent 运行时（默认是 `openclaw`） |
| `ASTRBOT_API_URL` | `http://host.docker.internal:6185` | Docker 容器访问宿主机必须用 `host.docker.internal`，不能用 `localhost` |
| `ASTRBOT_API_KEY` | `abk_xxx` | 第 2 步获取的 API Key |
| `ASTRBOT_TIMEOUT_SEC` | `300` | 请求超时时间（秒），可根据模型响应速度调整 |

### 3.2 为什么用 `host.docker.internal`？

Docker 容器有独立的网络命名空间。容器内的 `localhost` 指向容器自身，而不是你的 Windows 宿主机。Docker Desktop 提供了特殊域名 `host.docker.internal` 来访问宿主机服务。

---

## 4. 启动项目

### 4.1 构建并启动所有服务

在 `edict/` 目录下执行：

```bash
cd E:\gitwork\edict\edict
docker compose up -d --build
```

首次构建需要下载镜像和编译，约 3-5 分钟。

### 4.2 查看服务状态

```bash
docker compose ps
```

预期输出类似：

```
NAME                STATUS              PORTS
edict-postgres-1    Up (healthy)        0.0.0.0:5432->5432/tcp
edict-redis-1       Up (healthy)        0.0.0.0:6379->6379/tcp
edict-backend-1     Up                  0.0.0.0:7898->8000/tcp
edict-frontend-1    Up                  0.0.0.0:7899->3000/tcp
edict-orchestrator-1 Up
edict-dispatcher-1  Up
```

### 4.3 查看调度器日志（确认 AstrBot 连接）

```bash
docker compose logs dispatcher --tail 50 -f
```

正常启动时应看到类似日志：

```
DispatchWorker started | backend=astrbot | api_url=http://host.docker.internal:6185
```

---

## 5. 验证对接是否成功

### 5.1 检查后端 API

```bash
curl http://localhost:7898/api/v1/health
```

### 5.2 检查 AstrBot 连通性

从容器内部测试能否访问宿主机的 AstrBot：

```bash
docker compose exec dispatcher python -c "
import httpx, asyncio
async def test():
    async with httpx.AsyncClient() as c:
        r = await c.get('http://host.docker.internal:6185/')
        print(f'Status: {r.status_code}')
asyncio.run(test())
"
```

如果返回 `Status: 200`，说明网络连通。

### 5.3 创建测试任务

通过前端或 API 创建一个任务，观察 dispatcher 日志是否成功调用 AstrBot：

```bash
# 通过 API 创建测试任务
curl -X POST http://localhost:7898/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "测试AstrBot对接", "description": "请回复：收到"}'
```

然后在 dispatcher 日志中查找 AstrBot 响应：

```bash
docker compose logs dispatcher --tail 100 | grep -i astrbot
```

### 5.4 前端界面

浏览器访问：**http://localhost:7899**

可以在看板界面中创建任务、查看 Agent 响应和事件流转。

---

## 6. 常见问题

### Q: dispatcher 启动后报 `Connection refused` 或 `astrbot unreachable`

**原因**：容器无法访问宿主机的 AstrBot。

**排查**：
1. 确认 AstrBot 在宿主机上运行：`curl http://localhost:6185`
2. 确认 `ASTRBOT_API_URL` 使用的是 `http://host.docker.internal:6185`，不是 `localhost`
3. 检查 Windows 防火墙是否放行了 6185 端口
4. 如果 Docker Desktop 版本较旧不支持 `host.docker.internal`，尝试在 docker-compose.yml 中添加：

```yaml
dispatcher:
  extra_hosts:
    - "host.docker.internal:host-gateway"
```

### Q: AstrBot 返回 401 Unauthorized

**原因**：API Key 无效或未配置。

**排查**：
1. 确认 `ASTRBOT_API_KEY` 的值是以 `abk_` 开头的完整密钥
2. 确认该 Key 在 AstrBot 管理面板中仍然存在（未过期或被删除）
3. 确认该 Key 具有 `chat` 权限

### Q: 任务一直处于 dispatching 状态

**原因**：AstrBot 响应超时或 dispatcher 异常。

**排查**：
1. 查看 dispatcher 日志：`docker compose logs dispatcher --tail 200`
2. 检查 `ASTRBOT_TIMEOUT_SEC` 是否足够（默认 300 秒）
3. 如果 AstrBot 使用的模型响应慢，适当增大超时值

### Q: 想切回 OpenClaw 怎么办？

修改 docker-compose.yml 中 dispatcher 的 `DISPATCH_BACKEND` 为 `openclaw`，然后重启：

```bash
docker compose up -d dispatcher
```

### Q: 如何查看完整的事件流？

Redis Streams 中保存了所有事件：

```bash
docker compose exec redis redis-cli XREAD COUNT 10 STREAMS edict:events $
```

---

## 架构概览

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
│   Frontend   │────▶│   Backend    │────▶│  Redis Streams   │
│  :7899       │     │  :7898       │     │  (事件总线)       │
└─────────────┘     └──────┬───────┘     └────────┬─────────┘
                           │                       │
                    ┌──────▼───────┐        ┌──────▼─────────┐
                    │ Orchestrator │        │   Dispatcher   │
                    │ (编排决策)    │        │  (调度执行)     │
                    └──────────────┘        └──────┬─────────┘
                                                   │
                                          ┌────────▼────────┐
                                          │  Adapter 工厂    │
                                          └───┬─────────┬───┘
                                              │         │
                                     ┌────────▼──┐  ┌───▼────────┐
                                     │ OpenClaw  │  │  AstrBot   │
                                     │ Adapter   │  │  Adapter   │
                                     │ (CLI)     │  │ (HTTP API) │
                                     └───────────┘  └────────────┘
```

Edict 通过 Adapter 模式支持多种 Agent 运行时。当前支持：
- **OpenClaw**：通过 CLI 子进程调用
- **AstrBot**：通过 HTTP API（`/api/v1/chat`）调用，SSE 流式响应

通过 `DISPATCH_BACKEND` 环境变量选择运行时，无需修改代码。
