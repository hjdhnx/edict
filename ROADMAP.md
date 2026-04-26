# 三省六部 · Roadmap

这份路线图以当前可用主栈为准：Edict 已经具备 Docker Compose 启动、FastAPI 后端、Vue 3 总控台、Postgres/Redis、worker 调度链路，以及 AstrBot/OpenClaw 运行时适配。后续重点从“能跑起来”转向“更安全、更可靠、更适合团队长期使用”。

## Phase 1 — 本地可用主栈 ✅

- [x] 三省六部任务治理模型：太子、中书、门下、尚书、六部、回奏
- [x] 主状态链路：`Taizi -> Zhongshu -> Menxia -> Assigned -> Doing -> Review -> Done`
- [x] 任务创建、状态流转、进度上报、todo、奏折归档
- [x] FastAPI 后端与 `/api/live-status` 等看板接口
- [x] Postgres 持久化任务、报告、调度和审计数据
- [x] Redis Streams / PubSub 支撑事件与实时推送
- [x] Transactional Outbox、outbox relay、orchestrator、dispatcher worker
- [x] AstrBot adapter，默认 Docker Compose 派发后端为 AstrBot
- [x] OpenClaw adapter，作为可选 Agent runtime
- [x] Vue 3 + Pinia + Ant Design Vue + Vite 总控台
- [x] 白天/暗黑主题、紧凑布局、PC/移动端响应式
- [x] 固定侧边栏与顶部栏，仅内容区域滚动
- [x] 旨意看板、朝堂议政、省部调度、官员总览
- [x] 模型配置、技能配置、本地/远程技能管理
- [x] 执行进度、奏折阁、旨库、天下要闻、关于页
- [x] 天下要闻分类、关键词、自定义源、采集和 webhook 配置
- [x] 后端统一版本信息并展示到前端
- [x] 当前价值报告 V2 与关于页内容沉淀
- [x] Docker Compose 主栈：backend、frontend、postgres、redis、outbox-relay、orchestrator、dispatcher

## Phase 2 — 可靠性与治理深化 🚧

### 任务与调度可靠性

- [ ] 更完整的状态流转测试与迁移一致性检查
- [ ] 任务卡住后的可解释恢复建议
- [ ] dispatcher 失败原因结构化展示
- [ ] worker 健康状态与重试记录更细粒度可视化
- [ ] 长任务阶段隔离与执行 ownership 更清晰的建模

### 审议与人工介入

- [ ] 御批模式：人工审批、准奏、封驳
- [ ] 审议意见模板化与多轮审议记录优化
- [ ] 阻塞任务的人工裁决入口
- [ ] 高风险任务执行前确认机制

### 产物与知识沉淀

- [ ] 奏折导出为 Markdown / PDF
- [ ] 不同任务类型的完成规范
- [ ] 历史奏折检索、标签与复用
- [ ] 相似旨意推荐与经验沉淀

## Phase 3 — 安全与团队化

### 生产安全

- [ ] 用户认证与登录会话
- [ ] 角色权限与管理接口隔离
- [ ] API key、webhook、文件路径脱敏
- [ ] 审计日志、告警、备份和恢复
- [ ] 速率限制、任务配额和资源预算
- [ ] 外部 webhook 与远程技能来源治理

### 部署与发布

- [ ] 公共 demo 镜像或一键试用镜像
- [ ] CI 构建与版本发布流程
- [ ] 数据库迁移健康检查
- [ ] Windows / macOS / Linux 启动说明完善
- [ ] 生产部署示例：反向代理、HTTPS、备份策略

### 团队协作

- [ ] 多用户任务归属与可见性
- [ ] 通知中心与订阅规则
- [ ] GitHub Issues / Linear / Jira / Notion 集成
- [ ] Slack / Discord / 企业微信等消息入口

## Phase 4 — 体验与生态扩展

### 前端体验

- [ ] PWA 与移动端快捷入口
- [ ] 更细的可访问性优化
- [ ] 大任务活动流虚拟滚动
- [ ] 看板筛选、排序、批量操作增强
- [ ] 奏折阁全文预览与差异对比

### Skills 与 Agent 生态

- [ ] 官方远程技能库元数据治理
- [ ] 技能签名、来源校验和版本策略
- [ ] 任务模板市场或本地模板库导入导出
- [ ] 新 Agent 角色模板与行业化 SOUL.md

## 当前贡献优先级

1. 安全边界：认证、权限、密钥脱敏、限流。
2. 可靠性：状态机测试、worker 诊断、失败恢复。
3. 文档：当前 Docker/FastAPI/Vue/AstrBot 主路径的安装与排障。
4. 前端体验：紧凑布局、移动端适配、活动流可读性。
5. 生态：远程技能来源治理、模板体系、第三方集成。

## 参与方式

- 先阅读 [`README.md`](README.md) 和 [`docs/getting-started.md`](docs/getting-started.md)。
- 架构相关改动先阅读 [`docs/task-dispatch-architecture.md`](docs/task-dispatch-architecture.md)。
- AstrBot 相关改动先阅读 [`edict/docs/astrbot-integration-guide.md`](edict/docs/astrbot-integration-guide.md)。
- 提 PR 前按 [`CONTRIBUTING.md`](CONTRIBUTING.md) 运行构建与基本健康检查。
