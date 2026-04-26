# 远程 Skills 资源管理指南

Edict 支持在“技能配置”面板中管理本地技能、远程技能和内置技能仓库快选。远程 Skills 的目标是让 Agent 能力来源可见、可更新、可治理，而不是把技能散落在聊天记录或本机临时目录里。

## 当前推荐来源

推荐使用：

- GitHub raw URL
- 公开 HTTPS URL
- 项目内置的官方/常用技能仓库预设

谨慎使用：

- 本地文件路径
- 私有仓库临时下载链接
- 不可信网站上的 Markdown 文件

如果确实需要本地文件方式，请先确认当前 `scripts/skill_manager.py --help` 和运行时适配器支持，并确保路径中不包含敏感信息。

## 启动方式

```bash
cd edict
cp .env.example .env
docker compose up -d --build
```

访问：

- 前端技能配置：`http://127.0.0.1:7899` -> **技能配置**
- 后端 API：`http://127.0.0.1:7898`
- 前端代理 API：`http://127.0.0.1:7899/api/...`

## API 端点

### 添加远程 Skill

```bash
curl -X POST http://127.0.0.1:7898/api/add-remote-skill \
  -H "Content-Type: application/json" \
  -d '{
    "agentId": "zhongshu",
    "skillName": "code_review",
    "sourceUrl": "https://raw.githubusercontent.com/openclaw-ai/skills-hub/main/code_review/SKILL.md",
    "description": "代码审查专项技能"
  }'
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `agentId` | 目标 Agent ID，例如 `zhongshu`、`menxia`、`bingbu` |
| `skillName` | skill 内部名称，建议使用小写字母、数字、下划线 |
| `sourceUrl` | 可直接下载的 HTTPS / GitHub raw URL |
| `description` | 中文描述，可选 |

### 查看远程 Skills

```bash
curl http://127.0.0.1:7898/api/remote-skills-list
```

### 更新远程 Skill

```bash
curl -X POST http://127.0.0.1:7898/api/update-remote-skill \
  -H "Content-Type: application/json" \
  -d '{
    "agentId": "zhongshu",
    "skillName": "code_review"
  }'
```

### 移除远程 Skill

```bash
curl -X POST http://127.0.0.1:7898/api/remove-remote-skill \
  -H "Content-Type: application/json" \
  -d '{
    "agentId": "zhongshu",
    "skillName": "code_review"
  }'
```

## CLI 命令

CLI 适合批量导入、脚本化管理或排查 UI 问题。参数以当前脚本为准：

```bash
python3 scripts/skill_manager.py --help
```

常见示例：

```bash
python3 scripts/skill_manager.py add-remote \
  --agent zhongshu \
  --name code_review \
  --source https://raw.githubusercontent.com/openclaw-ai/skills-hub/main/code_review/SKILL.md \
  --description "代码审查专项技能"

python3 scripts/skill_manager.py list-remote

python3 scripts/skill_manager.py update-remote \
  --agent zhongshu \
  --name code_review

python3 scripts/skill_manager.py remove-remote \
  --agent zhongshu \
  --name code_review
```

## 看板 UI 操作

1. 打开 `http://127.0.0.1:7899`。
2. 进入 **技能配置**。
3. 查看本地技能、远程技能和内置远程技能仓库快选。
4. 选择一个预设技能，或手动填写远程 URL。
5. 选择目标 Agent。
6. 保存/导入。

导入后建议刷新列表确认状态，并查看后端日志排查下载失败：

```bash
docker compose logs backend --tail=100
```

## Skill 文件规范

远程 Skill 建议使用 Markdown + YAML frontmatter：

```markdown
---
name: code_review
description: 对代码进行结构、安全和可维护性审查
version: 1.0.0
tags: [code-review, security]
---

# 代码审查技能

## 输入

说明需要读取哪些文件、关注哪些问题。

## 处理流程

1. 识别语言和模块边界。
2. 检查安全、正确性、性能和可维护性。
3. 输出问题清单和建议。

## 输出规范

- 问题位置
- 严重程度
- 原因
- 修复建议
```

## 安全边界

远程 Skill 本质上是外部内容，应按供应链输入处理：

- 优先使用可信仓库。
- 使用固定 raw URL 或版本标签，避免来源漂移。
- 不导入未知来源的可执行脚本。
- 不在 Skill 中写入真实密钥、token、webhook。
- 对团队环境，后续应补充来源白名单、签名校验和审计记录。

## 故障排查

### 下载失败

```bash
curl -I https://raw.githubusercontent.com/openclaw-ai/skills-hub/main/code_review/SKILL.md
docker compose logs backend --tail=100
```

常见原因：

- 网络无法访问 GitHub raw。
- URL 不是原始文件地址。
- HTTPS 证书或代理配置异常。
- 文件过大或格式不符合要求。

### Skill 显示 invalid

检查：

- frontmatter 是否完整。
- `name` 是否和导入名称一致。
- Markdown 是否可正常解析。
- 后端日志是否记录了验证失败原因。

### 导入成功但 Agent 不使用

远程 Skill 管理只负责登记、下载和展示技能资源。实际任务是否使用该 Skill，取决于：

- 当前运行时（AstrBot/OpenClaw）的技能加载方式。
- 对应 Agent 的 SOUL.md / prompt 是否引用该技能。
- 任务提示是否触发相关能力。

## 最佳实践

- 为每个 Skill 写清适用 Agent、输入、处理流程和输出格式。
- 使用版本号管理变更。
- 对生产团队使用固定 commit/tag 的 raw URL。
- 删除不再使用的 Skill，避免 Agent 上下文污染。
- 定期审查远程来源可信度。

## 相关文档

- 快速入门：[`remote-skills-quickstart.md`](remote-skills-quickstart.md)
- 任务分发架构：[`task-dispatch-architecture.md`](task-dispatch-architecture.md)
- 快速上手：[`getting-started.md`](getting-started.md)
