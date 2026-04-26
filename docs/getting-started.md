# 快速上手指南

这份文档以当前可用主栈为准：`edict/docker-compose.yml` 启动 FastAPI 后端、Vue 3 前端、Postgres、Redis 和 worker，并默认通过 AstrBot 派发任务。OpenClaw 仍可作为可选运行时使用，但不再是新用户的必选第一步。

## 1. 准备环境

需要本机已有：

- Docker Desktop 或 Docker Engine
- Docker Compose
- 可访问的 AstrBot 实例（推荐默认路径）或 OpenClaw 环境（可选）

端口约定：

- 前端总控台：`http://127.0.0.1:7899`
- 后端 API：`http://127.0.0.1:7898`
- 后端健康检查：`http://127.0.0.1:7898/health`

## 2. 克隆项目并配置环境变量

```bash
git clone https://github.com/cft0808/edict.git
cd edict/edict
cp .env.example .env
```

如 AstrBot 跑在宿主机，Docker 容器内通常需要使用 `host.docker.internal`：

```env
DISPATCH_BACKEND=astrbot
ASTRBOT_API_URL=http://host.docker.internal:6185
ASTRBOT_API_KEY=你的 AstrBot API Key
```

如果你使用 OpenClaw，可改为：

```env
DISPATCH_BACKEND=openclaw
```

并确保 OpenClaw 侧 Agent、模型和权限已经配置好。

## 3. 启动 Edict

```bash
docker compose up -d --build
```

检查服务：

```bash
docker compose ps
curl http://127.0.0.1:7898/health
curl http://127.0.0.1:7899/api/live-status
```

打开浏览器：

```text
http://127.0.0.1:7899
```

当前主架构是 Docker Compose 编排的 FastAPI 后端（7898）+ Vue 3 前端（7899）+ Postgres + Redis + worker。

## 4. 发送第一道旨意

你可以在前端“旨意看板”直接下旨，也可以通过 AstrBot/OpenClaw 入口创建任务。

示例：

```text
请帮我调研这个项目的任务状态机：
1. 阅读 backend/app/models/task.py 和 frontend/src/stores/dashboard.ts
2. 说明状态列表和合法流转
3. 输出 Markdown 报告
4. 完成后上报报告路径和三句话摘要
```

任务主链路：

```text
Taizi -> Zhongshu -> Menxia -> Assigned -> Doing -> Review -> Done
```

其他状态包括：`Blocked`、`Cancelled`、`Pending`、`PendingConfirm`、`Next`。

## 5. 观察执行过程

进入总控台后重点看这些菜单：

- 旨意看板：查看任务卡片、状态、耗时、进度、todo、详情。
- 省部调度：查看各省部任务分布、Agent 状态、阻塞和派发情况。
- 执行进度：跟踪运行会话和过程活动。
- 奏折阁：任务完成后查看摘要、产物路径、正文预览和耗时。

## 进阶用法

### 使用旨库模板

路径：`旨库 -> 选择模板 -> 填写参数 -> 下旨`

适合周报、代码审查、API 设计、竞品分析、数据报告、博客文章、部署方案、邮件文案、站会摘要等高频任务。

### 管理模型

路径：`模型配置`

模型配置会保存 Edict 侧偏好，并尽量与当前运行时配置对齐。实际执行是否热切换，取决于当前 `DISPATCH_BACKEND` 和运行时适配器能力。

### 管理技能

路径：`技能配置`

支持查看本地技能、远程技能、内置远程技能仓库快选，并通过 HTTPS / GitHub raw 等来源导入技能。

### 订阅天下要闻

路径：`天下要闻 -> 订阅管理`

当前已支持分类、关键词、自定义信息源、采集和 webhook 配置。实际采集效果取决于网络环境和目标信息源可访问性；配置 webhook 后，满足条件的采集结果会按规则推送，未配置则不推送。

## 故障排查

### 看板显示“服务器未启动”

```bash
cd edict
docker compose ps
docker compose logs backend --tail=100
curl http://127.0.0.1:7898/health
```

### 前端能打开但数据不更新

```bash
docker compose logs backend --tail=100
docker compose logs outbox-relay --tail=100
docker compose logs orchestrator --tail=100
curl http://127.0.0.1:7899/api/live-status
```

### 任务创建后不自动流转

重点查看 dispatcher 和运行时配置：

```bash
docker compose logs dispatcher --tail=100
docker compose logs orchestrator --tail=100
```

确认 `.env` 中的配置与运行时一致：

```env
DISPATCH_BACKEND=astrbot
ASTRBOT_API_URL=http://host.docker.internal:6185
ASTRBOT_API_KEY=你的 AstrBot API Key
```

### AstrBot 连接失败

1. 确认宿主机 AstrBot 正在运行。
2. Docker Desktop 环境下优先使用 `http://host.docker.internal:6185`。
3. 检查 `ASTRBOT_API_KEY` 是否和 AstrBot 侧一致。
4. 查看 dispatcher 日志：

```bash
docker compose logs dispatcher --tail=100
```

### OpenClaw 运行时问题

如果使用 OpenClaw，请确认：

- `DISPATCH_BACKEND=openclaw`
- OpenClaw Gateway 已启动
- 相关 Agent 已注册并具备模型/API key
- Agent 按 Edict 协议上报状态、进度、todo 和完成产物

### 前端构建检查

```bash
cd edict/frontend
npm install
npm run build
```

## 更多资源

- 项目首页：[`../README.md`](../README.md)
- AstrBot 集成：[`../edict/docs/astrbot-integration-guide.md`](../edict/docs/astrbot-integration-guide.md)
- 任务架构：[`task-dispatch-architecture.md`](task-dispatch-architecture.md)
- 远程技能：[`remote-skills-guide.md`](remote-skills-guide.md)
- 当前价值报告：[`../edict/项目价值报告V2.md`](../edict/项目价值报告V2.md)
