# 参与贡献

三省六部欢迎任何形式的贡献：修文档、补测试、改 UI、完善运行时适配器、新增 Agent 规则或增强任务治理流程都可以。

## 报告 Bug

请使用 Bug Report 模板提交 Issue，并尽量包含：

- 操作系统与 Docker Desktop / Docker Engine 版本
- Docker Compose 版本
- 当前运行时：AstrBot 或 OpenClaw
- AstrBot/OpenClaw 版本与关键配置（不要贴真实密钥）
- 浏览器与前端截图（如果涉及 UI）
- `docker compose ps`
- 后端日志：`docker compose logs backend --tail=100`
- 派发日志：`docker compose logs dispatcher --tail=100`
- 复现步骤、期望行为、实际行为

## 功能建议

使用 Feature Request 模板。建议用“旨意”格式描述需求：

```text
目标：希望解决什么问题。
范围：涉及哪些页面、API、运行时或文档。
产物：希望最终交付什么。
验证：如何证明它可用。
```

## 提交 Pull Request

```bash
# 1. Fork 本仓库
# 2. 克隆你的 Fork
git clone https://github.com/<your-username>/edict.git
cd edict

# 3. 创建功能分支
git checkout -b feat/my-awesome-feature

# 4. 开发与验证
cd edict/frontend && npm run build
cd .. && docker compose up -d --build

# 5. 提交
git add <changed-files>
git commit -m "feat: 添加某个能力"

# 6. 推送并创建 PR
git push origin feat/my-awesome-feature
```

提交前请不要把 `.env`、真实 API key、webhook 地址或本地私密路径提交到仓库。

## 开发环境

### 前置条件

- Docker Desktop 或 Docker Engine
- Docker Compose
- Node.js 18+（前端开发/构建）
- Python 3.10+（后端开发/脚本）
- 可选：AstrBot 或 OpenClaw 运行时

### 本地启动

```bash
cd edict
cp .env.example .env
# 按需填写 ASTRBOT_API_URL / ASTRBOT_API_KEY
docker compose up -d --build
```

打开：

```text
http://127.0.0.1:7899
```

健康检查：

```bash
curl http://127.0.0.1:7898/health
curl http://127.0.0.1:7899/api/live-status
```

## 项目结构速览

| 目录/文件 | 说明 | 改动频率 |
| --- | --- | --- |
| `edict/frontend/src/` | Vue 3 + TypeScript + Ant Design Vue 总控台 | 高 |
| `edict/backend/app/` | FastAPI 后端、任务 API、服务、worker | 高 |
| `edict/migration/` | Alembic 数据库迁移 | 中 |
| `edict/scripts/kanban_update_edict.py` | Edict 看板 CLI 与任务上报协议 | 中 |
| `agents/*/SOUL.md` | 各省部 Agent 规则与角色纪律 | 中 |
| `docs/` | 根目录文档、架构、远程技能说明 | 中 |
| `edict/docs/` | 运行时集成文档 | 中 |
| `tests/` | 测试套件 | 中 |

## 测试与验证

### 前端

```bash
cd edict/frontend
npm install
npm run build
```

### 后端与主栈

```bash
cd edict
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:7898/health
curl http://127.0.0.1:7899/api/live-status
```

### 常用日志

```bash
cd edict
docker compose logs backend --tail=100
docker compose logs dispatcher --tail=100
docker compose logs orchestrator --tail=100
docker compose logs outbox-relay --tail=100
```

## 代码风格

- Python：遵循 PEP 8，优先使用 pathlib 处理路径。
- TypeScript/Vue：使用 Composition API 与 `<script setup lang="ts">`。
- UI：保持紧凑、高信息密度、移动端不横向溢出。
- CSS：优先复用全局 CSS 变量和已有布局类。
- Markdown：标题使用 `#`，列表使用 `-`，代码块标注语言。

## 特别欢迎的贡献方向

- UI 体验：紧凑布局、响应式、暗黑/白天主题、可访问性。
- 任务治理：状态机、审议、复核、归档、阻塞恢复。
- 运行时适配：AstrBot、OpenClaw 或其他 Agent runtime。
- Skills 生态：远程技能仓库、技能来源治理、技能模板。
- 外部集成：Notion、Jira、Linear、GitHub Issues、Webhook。
- 安全与生产化：认证、权限、密钥脱敏、限流、审计、备份。
- 文档：快速上手、架构说明、运行时集成、故障排查。

## 安全漏洞

发现安全问题请不要通过公开 Issue 报告。请按 [`SECURITY.md`](SECURITY.md) 中的方式处理。

## 行为准则

本项目采用 [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) 行为准则。参与本项目即表示你同意遵守其条款。
