# Edict 对接 AstrBot 指导手册

本文面向本地 Docker Desktop / Docker Compose 用户，说明如何让 Edict 通过 AstrBot 执行任务。当前 `edict/docker-compose.yml` 默认使用 AstrBot adapter。

## 1. 前置条件

| 条件 | 说明 |
| --- | --- |
| Docker Desktop / Docker Engine | 已安装并运行 |
| Docker Compose | 可执行 `docker compose` |
| AstrBot | 本地或内网可访问，常见地址为 `http://localhost:6185` |
| AstrBot API Key | 具备聊天接口权限 |

如果 AstrBot 运行在宿主机，Docker 容器内访问宿主机服务通常要使用：

```text
http://host.docker.internal:6185
```

不要在容器配置里写 `http://localhost:6185`，因为容器内的 `localhost` 指向容器自身。

## 2. 获取 AstrBot API Key

1. 浏览器打开 AstrBot 管理面板：`http://localhost:6185`。
2. 进入设置或 API Key 管理区域。
3. 创建新的 API Key。
4. 确认具备 chat / 对话接口权限。
5. 复制并保存 Key。

不要把真实 API Key 提交到仓库。

## 3. 配置 Edict

进入当前主栈目录：

```bash
cd edict
cp .env.example .env
```

编辑 `.env`：

```env
DISPATCH_BACKEND=astrbot
ASTRBOT_API_URL=http://host.docker.internal:6185
ASTRBOT_API_KEY=你的 AstrBot API Key
ASTRBOT_TIMEOUT_SEC=300
```

可选配置：

```env
ASTRBOT_CONFIG_ID=
ASTRBOT_CONFIG_NAME=
```

`ASTRBOT_CONFIG_ID` / `ASTRBOT_CONFIG_NAME` 用于指定 AstrBot WebChat 配置，让 HTTP API 会话尽量走与 WebUI / QQ 等入口一致的配置路由。二者通常填一个即可，优先使用 `ASTRBOT_CONFIG_ID`。

前端“模型配置”面板展示和保存的是 Edict 侧配置偏好；实际派发时是否使用指定 config，取决于 AstrBot adapter 当前读取的环境变量和 AstrBot 侧配置。

## 4. 启动项目

```bash
docker compose up -d --build
```

查看服务：

```bash
docker compose ps
```

预期应看到：

- `postgres`
- `redis`
- `backend`
- `frontend`
- `outbox-relay`
- `orchestrator`
- `dispatcher`

## 5. 验证

### 后端健康检查

```bash
curl http://localhost:7898/health
```

预期返回类似：

```json
{
  "status": "ok",
  "version": "V1.0.1",
  "versionLabel": "V1.0.1 20260426",
  "engine": "edict"
}
```

### 前端代理与看板数据

```bash
curl http://localhost:7899/api/live-status
```

### Dispatcher 日志

```bash
docker compose logs dispatcher --tail=100
```

重点查看是否出现 AstrBot 连接、401、timeout、connection refused 等信息。

### 容器内连通性

```bash
docker compose exec dispatcher python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:6185', timeout=5).status)"
```

如果返回 `200` 或 AstrBot 页面相关状态，说明容器可以访问宿主机 AstrBot。

## 6. 创建测试任务

可以在前端 `http://localhost:7899` 的“旨意看板”创建任务。创建后观察：

```bash
docker compose logs orchestrator --tail=100
docker compose logs dispatcher --tail=100
```

如果任务没有流转，优先确认：

- `.env` 中 `DISPATCH_BACKEND=astrbot`。
- `ASTRBOT_API_URL` 在容器内可访问。
- `ASTRBOT_API_KEY` 有效。
- AstrBot 当前模型和配置可正常回复。
- Agent 按 Edict 协议回写状态、进度和完成结果。

## 7. 常见问题

### dispatcher 报 Connection refused

排查：

1. 宿主机上确认 AstrBot 正在运行：

   ```bash
   curl http://localhost:6185
   ```

2. `.env` 中确认：

   ```env
   ASTRBOT_API_URL=http://host.docker.internal:6185
   ```

3. 检查 Windows 防火墙或 AstrBot 监听地址。

### AstrBot 返回 401 Unauthorized

排查：

- `ASTRBOT_API_KEY` 是否完整。
- Key 是否已过期或被删除。
- Key 是否具备聊天接口权限。
- `.env` 修改后是否重启了 dispatcher：

  ```bash
  docker compose up -d dispatcher
  ```

### 任务长时间没有进展

```bash
docker compose logs dispatcher --tail=200
docker compose logs orchestrator --tail=200
```

常见原因：

- AstrBot 模型响应慢，超过 `ASTRBOT_TIMEOUT_SEC`。
- AstrBot 当前配置没有可用模型。
- Agent 没有按 Edict 协议上报 progress / done。
- 任务进入 `Blocked` 或等待人工处理。

### 如何切换到 OpenClaw

编辑 `.env`：

```env
DISPATCH_BACKEND=openclaw
```

然后重启相关服务：

```bash
docker compose up -d dispatcher orchestrator
```

同时确认 OpenClaw 侧 Agent、模型、API key 和权限矩阵已配置好。

## 8. 架构关系

```text
Vue Frontend (:7899)
  -> FastAPI Backend (:7898)
    -> Redis / Postgres
    -> Orchestrator Worker
    -> Dispatcher Worker
      -> AstrBot Adapter
        -> AstrBot HTTP API (:6185)
```

Edict 负责任务治理、调度和审计；AstrBot 负责实际对话、模型调用和执行能力。两者之间的关键契约是：任务被派发后，Agent 需要把状态、进度、todo 和最终产物回写到 Edict。
