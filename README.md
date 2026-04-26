# 三省六部总控台 · Edict

Edict 是一个本地运行的 AI Agent 任务编排、治理与审计系统。它把用户的模糊指令转成可跟踪、可审议、可执行、可归档的多阶段任务，并通过 AstrBot / OpenClaw 等 Agent 运行时完成实际工作。

它不是普通聊天前端，也不只是古风皮肤。Edict 的核心价值是给 AI 长任务引入“制度”：每个任务有 ID、有阶段、有责任角色、有进度、有 todo、有流转日志，也有最终奏折。

## 当前定位

- 本地 AI Agent 工单系统
- 三省六部式任务治理层
- 可观察、可复盘的执行看板
- AstrBot / OpenClaw 等运行时的上层控制台

当前推荐部署方式是 `edict/docker-compose.yml`：

- 前端：Vue 3 + Pinia + Ant Design Vue + Vite + pino
- 后端：FastAPI + SQLAlchemy + Alembic
- 数据：Postgres + Redis
- Worker：outbox relay、orchestrator、dispatcher
- 默认运行时：AstrBot，OpenClaw 可选
- 前端端口：`7899`
- 后端端口：`7898`

> 根目录早期 demo、`dashboard/server.py`、`7891` 相关内容如仍保留，仅作为历史实现或旧演示参考，不是当前主启动方式。

## 为什么是三省六部

传统三省六部的价值在于分权、审议、执行和复核。Edict 借用这套结构，把 AI Agent 的工作从“一个模型直接回答”拆成更可控的流程：

```text
皇上/用户 -> 太子 -> 中书省 -> 门下省 -> 尚书省 -> 六部 -> 回奏
```

| 阶段 | 角色 | 产品含义 |
| --- | --- | --- |
| Taizi | 太子 | 分拣任务，判断方向和责任链路 |
| Zhongshu | 中书省 | 起草方案，拆解任务，形成计划 |
| Menxia | 门下省 | 审议方案，发现风险，必要时封驳 |
| Assigned | 尚书省 | 派发任务，决定执行部门 |
| Doing | 六部 | 执行具体工作，持续上报进展 |
| Review | 尚书省 | 汇总产物，复核结果 |
| Done | 回奏 | 完成任务，进入奏折归档 |

这套流程的重点是：规划和执行分离、审核和派发分离、过程和结果分离、聊天和工单分离。

## 快速启动

### 1. 准备环境

需要本机已有：

- Docker Desktop 或 Docker Engine
- Docker Compose
- 可选：AstrBot 或 OpenClaw 运行时

当前 Compose 默认使用 AstrBot。若 AstrBot 跑在宿主机，容器内通常使用 `http://host.docker.internal:6185` 访问。

### 2. 配置环境变量

```bash
cd edict
cp .env.example .env
```

如使用 AstrBot，编辑 `.env`：

```env
DISPATCH_BACKEND=astrbot
ASTRBOT_API_URL=http://host.docker.internal:6185
ASTRBOT_API_KEY=你的 AstrBot API Key
```

如使用 OpenClaw，可将 `DISPATCH_BACKEND` 改为 `openclaw`，并按对应运行时准备 Agent 环境。

### 3. 启动主栈

```bash
docker compose up -d --build
```

打开：

- 总控台：http://127.0.0.1:7899
- 后端健康检查：http://127.0.0.1:7898/health
- 后端 API：http://127.0.0.1:7898/api/live-status

### 4. 常用排查命令

```bash
cd edict
docker compose ps
docker compose logs backend --tail=100
docker compose logs dispatcher --tail=100
curl http://127.0.0.1:7898/health
curl http://127.0.0.1:7899/api/live-status
```

## 功能全景

当前前端菜单包括：

| 菜单 | 用途 |
| --- | --- |
| 旨意看板 | 创建和查看 Edict 任务，观察任务状态、进度、耗时、阻塞和归档入口 |
| 朝堂议政 | 召集多个官员/Agent 围绕主题讨论、推进、总结 |
| 省部调度 | 查看任务分布、Agent 状态、调度与阻塞情况 |
| 官员总览 | 查看各角色活跃度、完成数、耗时和统计信息 |
| 模型配置 | 管理各 Agent 的模型配置与 AstrBot/OpenClaw 相关偏好 |
| 技能配置 | 查看本地技能、远程技能、官方技能库快选和导入入口 |
| 执行进度 | 跟踪执行会话、任务过程和实时活动 |
| 奏折阁 | 查看已完成/取消任务的最终摘要、报告路径、正文预览和耗时 |
| 旨库 | 使用常见任务模板快速生成旨意 |
| 天下要闻 | 配置订阅分类、关键词、自定义信息源、采集和 webhook 推送 |
| 关于 | 查看项目定位、设计理念、用法、价值分析和边界说明 |

## 项目结构

```text
edict/
├── agents/                     # 各省部 Agent 规则与 SOUL.md
├── docs/                       # 根目录文档、架构说明、远程技能说明
├── edict/
│   ├── backend/                # FastAPI 后端、任务 API、模型、服务、worker
│   ├── frontend/               # Vue 3 总控台
│   ├── docs/                   # AstrBot 等运行时集成文档
│   ├── migration/              # Alembic 数据库迁移
│   ├── scripts/                # Edict CLI、任务上报和辅助脚本
│   ├── docker-compose.yml      # 当前主启动入口
│   └── 项目价值报告V2.md       # 当前推荐阅读的项目价值报告
├── scripts/                    # 历史/兼容脚本
├── tests/                      # 测试套件
├── README.md
├── CONTRIBUTING.md
└── ROADMAP.md
```

## 推荐使用方式

适合放进 Edict 的任务通常满足至少一个条件：

- 需要多步骤推进
- 需要过程中可见
- 需要不同角色审议
- 需要最终产物保存
- 需要之后复盘或复用

高质量旨意建议包含：

1. 范围：读哪些文件、处理哪些模块、调研哪些对象。
2. 目标：最终要解决什么问题。
3. 产物：输出 Markdown、代码、表格、清单还是报告。
4. 路径：产物保存到哪里。
5. 验证：完成后如何证明结果可用。

示例：

```text
阅读 frontend/src/stores/dashboard.ts 和 backend/app/models/task.py，说明 Edict 的任务状态机如何工作。
输出 Markdown 到 docs/state-machine-notes.md。
报告必须包含：状态列表、合法流转、前端展示方式、可能的风险点。
完成时上报文件路径和三句话摘要。
```

## 当前边界

Edict 当前更适合本机或可信内网使用，不建议直接公网暴露。

如果要对外开放或团队生产使用，需要先补齐：

- 用户认证和角色权限
- 管理接口隔离
- API key、webhook 和文件路径脱敏
- 访问日志、备份、告警和恢复机制
- 速率限制和任务配额
- 远程技能来源治理

同时，Edict 的执行可观测依赖 Agent 按协议上报状态、进度、todo 和完成产物。若运行时或 Agent 没有回写，前端不能凭空知道真实执行过程。

## 文档索引

- 快速上手：[`docs/getting-started.md`](docs/getting-started.md)
- AstrBot 集成：[`edict/docs/astrbot-integration-guide.md`](edict/docs/astrbot-integration-guide.md)
- 任务分发架构：[`docs/task-dispatch-architecture.md`](docs/task-dispatch-architecture.md)
- 远程技能指南：[`docs/remote-skills-guide.md`](docs/remote-skills-guide.md)
- 远程技能快速入门：[`docs/remote-skills-quickstart.md`](docs/remote-skills-quickstart.md)
- 当前价值报告：[`edict/项目价值报告V2.md`](edict/项目价值报告V2.md)
- 路线图：[`ROADMAP.md`](ROADMAP.md)
- 贡献指南：[`CONTRIBUTING.md`](CONTRIBUTING.md)

## License

MIT
