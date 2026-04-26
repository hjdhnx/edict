# 远程 Skills 快速入门

本文以当前主栈为准：通过 `edict/docker-compose.yml` 启动前端和后端，在“技能配置”面板管理远程 Skills。CLI 仍可用于高级场景；如脚本参数有变化，请以 `python3 scripts/skill_manager.py --help` 为准。

## 1. 启动 Edict

```bash
cd edict
cp .env.example .env
# 按需填写 AstrBot / OpenClaw 配置
docker compose up -d --build
```

打开：

- 前端总控台：http://127.0.0.1:7899
- 后端 API：http://127.0.0.1:7898

检查：

```bash
curl http://127.0.0.1:7898/health
curl http://127.0.0.1:7899/api/live-status
```

## 2. 通过看板添加 Remote Skill

1. 打开 `http://127.0.0.1:7899`。
2. 进入 **技能配置**。
3. 选择远程技能相关区域或内置远程技能仓库快选。
4. 选择目标 Agent。
5. 填写 Skill 名称、远程 URL 和描述。
6. 点击导入/保存。

推荐来源：

- HTTPS URL
- GitHub raw URL
- 已在界面内置的官方/常用技能仓库预设

不建议把本机私密路径当作“远程技能来源”。如果确实需要本地文件方式，请先确认当前脚本和运行时支持，并注意路径不会泄露敏感内容。

## 3. 通过 API 添加 Remote Skill

直连后端：

```bash
curl -X POST http://127.0.0.1:7898/api/add-remote-skill \
  -H "Content-Type: application/json" \
  -d '{
    "agentId": "zhongshu",
    "skillName": "code_review",
    "sourceUrl": "https://raw.githubusercontent.com/openclaw-ai/skills-hub/main/code_review/SKILL.md",
    "description": "代码审查能力"
  }'
```

通过前端代理：

```bash
curl -X POST http://127.0.0.1:7899/api/add-remote-skill \
  -H "Content-Type: application/json" \
  -d '{
    "agentId": "zhongshu",
    "skillName": "code_review",
    "sourceUrl": "https://raw.githubusercontent.com/openclaw-ai/skills-hub/main/code_review/SKILL.md",
    "description": "代码审查能力"
  }'
```

查看列表：

```bash
curl http://127.0.0.1:7898/api/remote-skills-list
```

更新：

```bash
curl -X POST http://127.0.0.1:7898/api/update-remote-skill \
  -H "Content-Type: application/json" \
  -d '{
    "agentId": "zhongshu",
    "skillName": "code_review"
  }'
```

移除：

```bash
curl -X POST http://127.0.0.1:7898/api/remove-remote-skill \
  -H "Content-Type: application/json" \
  -d '{
    "agentId": "zhongshu",
    "skillName": "code_review"
  }'
```

## 4. 通过 CLI 管理

```bash
python3 scripts/skill_manager.py --help
```

常见命令示例：

```bash
python3 scripts/skill_manager.py add-remote \
  --agent zhongshu \
  --name code_review \
  --source https://raw.githubusercontent.com/openclaw-ai/skills-hub/main/code_review/SKILL.md \
  --description "代码审查能力"

python3 scripts/skill_manager.py list-remote

python3 scripts/skill_manager.py update-remote \
  --agent zhongshu \
  --name code_review

python3 scripts/skill_manager.py remove-remote \
  --agent zhongshu \
  --name code_review
```

## 5. 创建自己的 Skill 仓库

推荐结构：

```text
my-skills-hub/
├── code_review/
│   └── SKILL.md
├── api_design/
│   └── SKILL.md
└── README.md
```

`SKILL.md` 示例：

```markdown
---
name: my_custom_skill
description: 简短描述
version: 1.0.0
tags: [tag1, tag2]
---

# Skill 完整名称

## 输入

说明接收什么参数。

## 处理流程

具体步骤。

## 输出规范

输出格式说明。
```

推送到 GitHub 后，用 raw URL 导入：

```text
https://raw.githubusercontent.com/<user>/<repo>/<branch>/<skill>/SKILL.md
```

## 6. 故障排查

### 下载失败

```bash
curl -I https://raw.githubusercontent.com/openclaw-ai/skills-hub/main/code_review/SKILL.md
```

常见原因：

- 网络无法访问 GitHub raw。
- URL 不是可直接下载的原始文件地址。
- Skill 文件格式不符合要求。

### 导入后看不到

```bash
curl http://127.0.0.1:7898/api/remote-skills-list
docker compose logs backend --tail=100
```

同时刷新前端“技能配置”面板。

### 运行时没有使用新技能

远程技能导入只负责把 Skill 资源登记/下载到对应位置。实际执行时是否使用该技能，取决于当前 Agent runtime、Agent 规则和任务提示是否会读取这些技能。

## 更多信息

- 完整指南：[`remote-skills-guide.md`](remote-skills-guide.md)
- 任务架构：[`task-dispatch-architecture.md`](task-dispatch-architecture.md)
- AstrBot 集成：[`../edict/docs/astrbot-integration-guide.md`](../edict/docs/astrbot-integration-guide.md)
