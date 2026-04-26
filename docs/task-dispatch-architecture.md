# Edict 任务分发流转架构

本文档说明 Edict 如何把一条用户指令变成可观察、可审议、可执行、可归档的多阶段任务。当前主栈是 FastAPI 后端、Vue 3 总控台、Postgres、Redis、worker 调度链路，并通过 AstrBot / OpenClaw adapter 调用外部 Agent runtime。

## 1. 业务模型：用制度管理 Agent 不确定性

Edict 采用“三省六部”作为任务治理模型，而不是让多个 Agent 自由聊天后直接给结果。

```text
用户/皇上
  -> 太子 Taizi：分拣任务，判断责任链路
  -> 中书省 Zhongshu：起草方案，拆解任务
  -> 门下省 Menxia：审议方案，发现风险，必要时封驳
  -> 尚书省 Assigned：派发任务，决定执行部门
  -> 六部 Doing：执行具体工作，持续上报进展
  -> 尚书省 Review：汇总产物，复核结果
  -> 回奏 Done：形成奏折并归档
```

核心目标：

- 规划和执行分离，避免 Agent 一上来就动手。
- 审议和派发分离，让风险在执行前暴露。
- 过程和结果分离，既看最终产物，也看过程是否可靠。
- 聊天和工单分离，让长任务可追踪、可复盘。

## 2. 当前技术架构

```text
Vue 3 Frontend (:7899)
  -> FastAPI Backend (:7898)
    -> Postgres：任务、报告、配置、审计数据
    -> Redis Streams / PubSub：事件总线与实时推送
    -> Outbox Relay：可靠事件投递
    -> Orchestrator Worker：根据状态决定下一步
    -> Dispatcher Worker：调用 Agent runtime adapter
      -> AstrBot Adapter：HTTP API，当前 Docker Compose 默认
      -> OpenClaw Adapter：CLI / runtime 集成，可选
```

### 关键服务

| 服务 | 职责 |
| --- | --- |
| `backend` | FastAPI API、WebSocket、任务读写、配置管理 |
| `frontend` | Vue 3 总控台，展示看板、奏折、模型、技能、天下要闻等页面 |
| `postgres` | 持久化任务、报告、调度、配置和审计数据 |
| `redis` | Streams / PubSub，支撑事件驱动与实时刷新 |
| `outbox-relay` | 从 outbox 表可靠投递事件到 Redis |
| `orchestrator` | 消费任务事件，推进状态和派发决策 |
| `dispatcher` | 调用 AstrBot/OpenClaw 等运行时执行具体工作 |

## 3. 状态机

主路径：

```text
Taizi -> Zhongshu -> Menxia -> Assigned -> Doing -> Review -> Done
```

常见状态：

| 状态 | 含义 |
| --- | --- |
| `Pending` | 兼容/待处理状态，通常会进入太子分拣 |
| `Taizi` | 太子分拣，判断是否为正式旨意和责任链路 |
| `Zhongshu` | 中书省起草方案、拆解任务 |
| `Menxia` | 门下省审议，可通过或封驳 |
| `Assigned` | 尚书省准备派发 |
| `Next` | 待执行队列，用于兼容或排队场景 |
| `Doing` | 六部或目标执行者正在处理 |
| `Review` | 尚书省汇总和复核 |
| `Done` | 完成并进入奏折归档 |
| `Blocked` | 阻塞，需要人工或调度介入 |
| `Cancelled` | 已取消，终态 |
| `PendingConfirm` | 等待确认的中间状态，用于需要人工确认的场景 |

## 4. 任务数据与可观测性

一个 Edict 任务通常包含：

- 基本信息：ID、标题、描述、优先级、当前状态、当前部门。
- 流转记录：状态从哪里到哪里，原因是什么。
- 进度记录：Agent 在关键节点上报当前工作。
- todo 快照：任务拆解、完成比例、当前阻塞点。
- 调度元数据：派发状态、重试、超时、错误信息。
- 奏折信息：摘要、产物路径、正文预览、耗时。

前端重点页面：

| 页面 | 观察问题 |
| --- | --- |
| 旨意看板 | 任务在哪个阶段、是否阻塞、耗时多少、下一步是谁 |
| 执行进度 | 当前执行会话、活动和过程记录 |
| 省部调度 | 各状态/部门分布、Agent 健康和派发情况 |
| 奏折阁 | 最终产物、摘要、报告路径、耗时和归档记录 |

## 5. API 与实时通道

当前 FastAPI 主入口包括：

- `GET /health`：后端健康检查和版本信息。
- `/api/live-status`：前端主看板数据，兼容旧前端数据结构。
- `/api/tasks`：任务相关 API。
- `/api/agents`：Agent、模型、技能等相关信息。
- `/api/events`：事件相关接口。
- `/api/admin`：管理类接口。
- `/ws`：WebSocket 实时通道。

前端通过 `7899` 访问时，可使用前端代理路径，例如：

```bash
curl http://127.0.0.1:7899/api/live-status
```

直连后端时使用：

```bash
curl http://127.0.0.1:7898/health
curl http://127.0.0.1:7898/api/live-status
```

## 6. Agent runtime adapter

Edict 自己不是模型服务。它负责任务治理、调度和审计，实际推理与工具调用由外部运行时完成。

### AstrBot adapter

当前 Docker Compose 默认：

```env
DISPATCH_BACKEND=astrbot
ASTRBOT_API_URL=http://host.docker.internal:6185
ASTRBOT_API_KEY=...
```

适合 Windows Docker Desktop + 宿主机 AstrBot 的本地部署方式。

### OpenClaw adapter

可选运行时：

```env
DISPATCH_BACKEND=openclaw
```

适合已有 OpenClaw Agent 工作区和 CLI 运行环境的用户。

## 7. 上报协议

为了让看板真实可观测，Agent 必须按协议上报：

- 开始处理时上报 progress。
- 阶段变化时走合法状态流转。
- 长任务定期更新 progress 和 todo。
- 阻塞时写清 block 原因。
- 完成时保存产物路径、摘要和报告正文，进入 Done。

如果 Agent 只在聊天里说“完成了”，但没有回写状态和产物，Edict 无法自动生成准确的看板进度和奏折。

## 8. Workflow state vs execution ownership

Edict 中有两个相关但不同的概念：

- **workflow state**：任务在制度流程中的阶段，例如 `Assigned`、`Doing`、`Review`。
- **execution ownership**：当前实际 runtime 会话或 Agent 派发链路中，谁持有下一步动作。

简单流程里二者通常一致；复杂任务、重试、封驳或多阶段派发时，二者可能短暂不一致。

这个区分有助于排查：

- 为什么 UI 已显示到后续阶段，但某个早期执行上下文仍在写进度。
- 为什么一次派发成功不等于后续所有阶段都已经独立接管。
- 后续如何设计更严格的阶段隔离和 ownership 转移。

## 9. 常见故障与排查

### 任务创建后不流转

```bash
cd edict
docker compose logs orchestrator --tail=100
docker compose logs dispatcher --tail=100
```

检查：

- worker 是否启动。
- `DISPATCH_BACKEND` 是否正确。
- AstrBot/OpenClaw 是否可访问。
- Agent 是否按协议上报状态。

### AstrBot 连接失败

```bash
curl http://127.0.0.1:7898/health
docker compose logs dispatcher --tail=100
```

Windows Docker Desktop 中，容器访问宿主机 AstrBot 通常应使用：

```env
ASTRBOT_API_URL=http://host.docker.internal:6185
```

### 看板数据不刷新

```bash
docker compose logs backend --tail=100
docker compose logs outbox-relay --tail=100
curl http://127.0.0.1:7899/api/live-status
```

## 10. 设计取舍

Edict 的核心价值不是替代 AstrBot/OpenClaw，而是在它们之上补齐：

- 谁来执行。
- 按什么流程执行。
- 执行到哪一步。
- 是否需要审议或复核。
- 最终产物如何归档。
- 出问题时如何定位卡点。

因此，当前最准确的定位是：本地 AI Agent 工单系统、任务治理层和审计看板。
