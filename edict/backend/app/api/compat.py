"""Compatibility API — 扁平路由兼容层，桥接前端 api.ts 与新版 RESTful 后端。

前端 api.ts 调用旧版 dashboard/server.py 的扁平路径（如 /api/live-status），
而后端新架构使用 /api/tasks/* 等命名空间路由。本模块注册所有前端期望的扁平路径，
复用现有 service 层逻辑，让前端无需修改即可正常工作。
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from ..adapters import create_adapter
from ..config import get_settings
from ..db import get_db
from ..models.task import TaskState
from ..services.event_bus import EventBus, get_event_bus, TOPIC_TASK_DISPATCH
from ..services.morning_brief import DEFAULT_CATEGORIES, collect_morning_brief, normalize_morning_config, push_morning_brief
from ..services.task_service import TaskService

log = logging.getLogger("edict.api.compat")
router = APIRouter()

# ── Agent 元信息（前端 store.ts DEPTS 对齐） ──

AGENT_DEFS: list[dict] = [
    {"id": "taizi",    "label": "太子",   "emoji": "🤴", "role": "太子",     "rank": "储君"},
    {"id": "zhongshu", "label": "中书省", "emoji": "📜", "role": "中书令",   "rank": "正一品"},
    {"id": "menxia",   "label": "门下省", "emoji": "🔍", "role": "侍中",     "rank": "正一品"},
    {"id": "shangshu", "label": "尚书省", "emoji": "📮", "role": "尚书令",   "rank": "正一品"},
    {"id": "libu",     "label": "礼部",   "emoji": "📝", "role": "礼部尚书", "rank": "正二品"},
    {"id": "hubu",     "label": "户部",   "emoji": "💰", "role": "户部尚书", "rank": "正二品"},
    {"id": "bingbu",   "label": "兵部",   "emoji": "⚔️", "role": "兵部尚书", "rank": "正二品"},
    {"id": "xingbu",   "label": "刑部",   "emoji": "⚖️", "role": "刑部尚书", "rank": "正二品"},
    {"id": "gongbu",   "label": "工部",   "emoji": "🔧", "role": "工部尚书", "rank": "正二品"},
    {"id": "libu_hr",  "label": "吏部",   "emoji": "👔", "role": "吏部尚书", "rank": "正二品"},
    {"id": "zaochao",  "label": "钦天监", "emoji": "📰", "role": "朝报官",   "rank": "正三品"},
]

AGENT_META_MAP: dict[str, dict] = {
    "zaochao":  {"name": "早朝（朝会主持）", "role": "朝会召集与议程管理", "icon": "🏛️"},
    "shangshu": {"name": "尚书令",           "role": "总协调与任务监督",   "icon": "📜"},
    "zhongshu": {"name": "中书省",           "role": "起草诏令与方案规划", "icon": "✍️"},
    "menxia":   {"name": "门下省",           "role": "审核与封驳",         "icon": "🔍"},
    "libu":     {"name": "吏部",             "role": "人事与组织管理",     "icon": "👤"},
    "hubu":     {"name": "户部",             "role": "财务与资源管理",     "icon": "💰"},
    "gongbu":   {"name": "工部",             "role": "工程与技术实施",     "icon": "🔧"},
    "xingbu":   {"name": "刑部",             "role": "规范与质量审查",     "icon": "⚖️"},
    "bingbu":   {"name": "兵部",             "role": "安全与应急响应",     "icon": "🛡️"},
}

# ── Helpers ──

def _resolve_project_root() -> Path:
    here = Path(__file__).resolve()
    candidates = [Path.cwd(), *here.parents]
    for candidate in candidates:
        if (candidate / "agents").exists() or (candidate / "data").exists():
            return candidate
    return Path.cwd()


# 路径兼容本地源码布局与容器内 /app/app/api 布局
_PROJECT_ROOT = _resolve_project_root()
AGENTS_DIR = _PROJECT_ROOT / "agents"
DATA_DIR = _PROJECT_ROOT / "data"
AGENT_CONFIG_PATH = DATA_DIR / "agent_config.json"
MORNING_CONFIG_PATH = DATA_DIR / "morning_config.json"
MORNING_BRIEF_PATH = DATA_DIR / "morning_brief.json"
MODEL_CHANGE_LOG_LIMIT = 100

DEFAULT_KNOWN_MODELS = [
    {"id": "default", "label": "Default", "provider": "system"},
    {"id": "anthropic/claude-sonnet-4-6", "label": "Claude Sonnet 4.6", "provider": "Anthropic"},
    {"id": "anthropic/claude-opus-4-7", "label": "Claude Opus 4.7", "provider": "Anthropic"},
    {"id": "openai/gpt-4o", "label": "GPT-4o", "provider": "OpenAI"},
    {"id": "openai/gpt-4o-mini", "label": "GPT-4o Mini", "provider": "OpenAI"},
]

DEFAULT_MORNING_CONFIG = {
    "categories": [{"name": name, "enabled": True} for name in DEFAULT_CATEGORIES],
    "keywords": [],
    "custom_feeds": [],
    "wecom_webhook": "",
    "feishu_webhook": "",
    "enabled": True,
    "message": "暂无天下要闻数据，请点击立即采集。",
}

_morning_refresh_lock = asyncio.Lock()
_morning_refresh_running = False


def _get_svc(db: AsyncSession = Depends(get_db)) -> TaskService:
    return TaskService(db, None)


def _read_json(path: Path, default: Any) -> Any:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            log.warning("Failed to read JSON config from %s", path)
    return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_agent_config_json() -> dict:
    """加载 data/agent_config.json（若存在）。"""
    data = _read_json(AGENT_CONFIG_PATH, {})
    return data if isinstance(data, dict) else {}


def _agent_entries(saved_configs: dict) -> dict[str, dict]:
    entries: dict[str, dict] = {}
    for item in saved_configs.get("agents", []):
        if isinstance(item, dict) and item.get("id"):
            entries[str(item["id"])] = item
    for agent_id in AGENT_META_MAP:
        legacy = saved_configs.get(agent_id)
        if isinstance(legacy, dict):
            entries.setdefault(agent_id, {}).update(legacy)
    return entries


def _workspace_skill_dir(agent_id: str) -> Path:
    return Path.home() / ".openclaw" / f"workspace-{agent_id}" / "skills"


def _safe_skill_name(name: str) -> str:
    value = "".join(ch for ch in name.strip() if ch.isalnum() or ch in ("-", "_", "."))[:80]
    return value.strip(".")


def _list_skills_for_agent(agent_id: str, cfg: dict | None = None) -> list[dict]:
    skills: list[dict] = []
    seen: set[str] = set()
    for item in (cfg or {}).get("skills", []) if isinstance(cfg, dict) else []:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        name = str(item["name"])
        seen.add(name)
        skills.append({
            "name": name,
            "description": str(item.get("description") or ""),
            "path": str(item.get("path") or ""),
        })
    for skills_dir in (AGENTS_DIR / agent_id / "skills", _workspace_skill_dir(agent_id)):
        if not skills_dir.is_dir():
            continue
        for f in sorted(skills_dir.iterdir()):
            skill_file = f / "SKILL.md" if f.is_dir() else f
            if skill_file.suffix not in (".md", ".txt", ".js") or not skill_file.exists():
                continue
            name = f.name if f.is_dir() else f.stem
            if name in seen:
                continue
            seen.add(name)
            skills.append({"name": name, "description": "", "path": str(skill_file)})
    return skills


async def _load_astrbot_models() -> tuple[list[dict], str, str]:
    settings = get_settings()
    if not settings.astrbot_api_url or not settings.astrbot_api_key:
        return [], "local", "AstrBot API 未配置"
    headers = {"Authorization": f"Bearer {settings.astrbot_api_key}", "X-API-Key": settings.astrbot_api_key}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.astrbot_api_url.rstrip('/')}/api/v1/configs", headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        log.warning("AstrBot config list unavailable: %s", exc)
        return [], "local", "AstrBot 暂不可达，已回退本地模型列表"
    configs = ((data.get("data") or {}).get("configs") or []) if isinstance(data, dict) else []
    models = []
    for item in configs:
        if not isinstance(item, dict):
            continue
        config_id = str(item.get("id") or "").strip()
        if not config_id:
            continue
        name = str(item.get("name") or config_id).strip()
        models.append({
            "id": f"astrbot-config:{config_id}",
            "label": f"AstrBot 配置：{name}",
            "provider": "AstrBot",
            "source": "astrbot-configs",
            "configId": config_id,
            "configName": name,
            "isDefault": bool(item.get("is_default")),
        })
    return models, "astrbot-configs", f"已从 AstrBot 读取 {len(models)} 个配置" if models else "AstrBot 未返回配置"


# ══════════════════════════════════════════
# Priority 1 — 前端加载必需
# ══════════════════════════════════════════

@router.get("/api/live-status")
async def live_status(svc: TaskService = Depends(_get_svc)):
    """兼容旧 /api/live-status — 返回 {tasks: Task[], syncStatus: {ok: bool}}。"""
    raw = await svc.get_live_status()
    active = list(raw.get("tasks", {}).values())
    completed = list(raw.get("completed_tasks", {}).values())
    return {
        "tasks": active + completed,
        "syncStatus": {"ok": True},
    }


@router.get("/api/agent-config")
async def agent_config():
    """兼容旧 /api/agent-config — 返回 agents + skills + models。"""
    saved_configs = _load_agent_config_json()
    saved_agents = _agent_entries(saved_configs)
    agents = []
    for agent_id, meta in AGENT_META_MAP.items():
        cfg = saved_agents.get(agent_id, {})
        model = str(cfg.get("model") or cfg.get("modelId") or "default")
        agents.append({
            "id": agent_id,
            "label": meta["name"],
            "emoji": meta["icon"],
            "role": meta["role"],
            "model": model,
            "skills": _list_skills_for_agent(agent_id, cfg),
        })

    astrbot_models, model_source, model_message = await _load_astrbot_models()
    local_models = saved_configs.get("knownModels") or saved_configs.get("_known_models") or DEFAULT_KNOWN_MODELS
    known_models = astrbot_models or local_models
    dispatch_channel = saved_configs.get("dispatchChannel") or saved_configs.get("_dispatch_channel") or get_settings().default_dispatch_channel
    return {
        "agents": agents,
        "knownModels": known_models,
        "modelSource": model_source,
        "modelSourceMessage": model_message,
        "dispatchChannel": dispatch_channel,
    }


@router.get("/api/agents-status")
async def agents_status(db: AsyncSession = Depends(get_db)):
    """Agent 状态 — 基于数据库实际任务判断各 agent 当前状态。

    running: 有正在处理的任务（Doing/Review/Assigned 等活跃状态）
    idle: 有历史任务但当前无活跃任务
    offline: 从未处理过任何任务
    """
    from sqlalchemy import func, case, select as sa_select
    from ..models.task import Task, STATE_AGENT_MAP, ORG_AGENT_MAP

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    # 活跃状态集合
    ACTIVE_STATES = [TaskState.Doing, TaskState.Review, TaskState.Assigned,
                     TaskState.Next, TaskState.Taizi, TaskState.Zhongshu, TaskState.Menxia]

    # 查所有未归档任务
    stmt = sa_select(Task.state, Task.org, Task.updated_at).where(Task.archived == False)  # noqa: E712
    result = await db.execute(stmt)
    all_tasks = result.all()

    # 构建每个 agent 的统计
    agent_status: dict[str, dict] = {}
    for d in AGENT_DEFS:
        agent_status[d["id"]] = {"active_tasks": 0, "total_tasks": 0, "last_active": None}

    # 状态 → agent 映射（反向）
    STATE_TO_AGENTS: dict[str, list[str]] = {}
    for st, ag in STATE_AGENT_MAP.items():
        STATE_TO_AGENTS.setdefault(st.value, []).append(ag)

    for task in all_tasks:
        state_val = task.state.value if isinstance(task.state, TaskState) else str(task.state)
        org = task.org or ""
        is_active = state_val in {s.value for s in ACTIVE_STATES}
        updated = task.updated_at

        # 找负责的 agent
        agents_for_task = []

        # 按状态映射
        if state_val in STATE_TO_AGENTS:
            agents_for_task.extend(STATE_TO_AGENTS[state_val])

        # 按部门映射（Doing/Next 状态的六部任务）
        if state_val in ("Doing", "Next") and org in ORG_AGENT_MAP:
            dept_agent = ORG_AGENT_MAP[org]
            if dept_agent not in agents_for_task:
                agents_for_task = [dept_agent]

        # 如果没找到对应 agent，按 org 名映射
        if not agents_for_task:
            for d in AGENT_DEFS:
                if d["label"] == org:
                    agents_for_task = [d["id"]]
                    break

        for ag_id in agents_for_task:
            if ag_id in agent_status:
                agent_status[ag_id]["total_tasks"] += 1
                if is_active:
                    agent_status[ag_id]["active_tasks"] += 1
                if updated:
                    prev = agent_status[ag_id]["last_active"]
                    if prev is None or updated > prev:
                        agent_status[ag_id]["last_active"] = updated

    # 检查 AstrBot 是否可达
    gateway_alive = False
    gateway_status = "disconnected"
    try:
        import httpx
        settings = get_settings()
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.astrbot_api_url}/")
            gateway_alive = resp.status_code == 200
            gateway_status = "connected" if gateway_alive else "error"
    except Exception:
        gateway_status = "offline"

    agents = []
    for d in AGENT_DEFS:
        aid = d["id"]
        stat = agent_status.get(aid, {})
        active = stat.get("active_tasks", 0)
        total = stat.get("total_tasks", 0)
        last = stat.get("last_active")

        if active > 0:
            status, label = "running", "执行中"
        elif total > 0:
            status, label = "idle", "待命"
        else:
            status, label = "idle", "待命"

        agents.append({
            "id": aid,
            "label": d["label"],
            "emoji": d["emoji"],
            "role": d["role"],
            "status": status,
            "statusLabel": label,
            "lastActive": last.isoformat() if last else None,
        })

    return {
        "ok": True,
        "gateway": {"alive": gateway_alive, "probe": gateway_alive, "status": gateway_status},
        "agents": agents,
        "checkedAt": now_iso,
    }


# ══════════════════════════════════════════
# Priority 2 — 核心功能
# ══════════════════════════════════════════

# ── Create Task ──

class CompatCreateTask(BaseModel):
    title: str
    org: str = ""
    official: str = ""
    priority: str = "中"
    templateId: str | None = None
    params: dict | None = None
    targetDept: str | None = None


@router.post("/api/create-task")
async def create_task(body: CompatCreateTask, svc: TaskService = Depends(_get_svc)):
    """兼容旧 /api/create-task。"""
    tags = []
    if body.org:
        tags.append(f"org:{body.org}")
    if body.templateId:
        tags.append(f"tpl:{body.templateId}")
    meta = {}
    if body.params:
        meta["params"] = body.params
    if body.targetDept:
        meta["targetDept"] = body.targetDept

    task = await svc.create_task(
        title=body.title,
        description="",
        priority=body.priority,
        assignee_org=body.org or None,
        creator=body.official or "emperor",
        tags=tags,
        meta=meta or None,
    )
    return {"ok": True, "taskId": str(task.task_id)}


# ── Task Action ──

class TaskActionBody(BaseModel):
    taskId: str
    action: str
    reason: str = ""


@router.post("/api/task-action")
async def task_action(body: TaskActionBody, svc: TaskService = Depends(_get_svc)):
    """兼容旧 /api/task-action — 执行状态流转。"""
    action_map = {
        "advance": "Zhongshu",
        "approve": "Menxia",
        "reject": "Zhongshu",
        "dispatch": "Assigned",
        "complete": "Done",
        "cancel": "Cancelled",
        "block": "Blocked",
    }
    new_state = action_map.get(body.action, body.action)
    try:
        st = TaskState(new_state)
    except ValueError:
        return {"ok": False, "error": f"Unknown action: {body.action}"}

    try:
        task = await svc.transition_state(
            task_id=uuid.UUID(body.taskId),
            new_state=st,
            agent="system",
            reason=body.reason,
        )
        return {"ok": True, "message": f"Task {body.action}"}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


# ── Archive Task ──

class ArchiveTaskBody(BaseModel):
    taskId: str | None = None
    archived: bool | None = None
    archiveAllDone: bool = False


@router.post("/api/archive-task")
async def archive_task(body: ArchiveTaskBody, svc: TaskService = Depends(_get_svc)):
    """兼容旧 /api/archive-task。"""
    if body.archiveAllDone:
        tasks = await svc.list_tasks(limit=200)
        count = 0
        for t in tasks:
            if t.state.value == "Done" and not t.archived:
                t.archived = True
                count += 1
        await svc.db.commit()
        return {"ok": True, "count": count}

    if body.taskId:
        try:
            task = await svc.get_task(uuid.UUID(body.taskId))
            task.archived = body.archived if body.archived is not None else True
            await svc.db.commit()
            return {"ok": True}
        except ValueError:
            return {"ok": False, "error": "Task not found"}
    return {"ok": False, "error": "Missing taskId"}


# ── Advance State ──

class AdvanceStateBody(BaseModel):
    taskId: str
    comment: str = ""


@router.post("/api/advance-state")
async def advance_state(body: AdvanceStateBody, svc: TaskService = Depends(_get_svc)):
    """兼容旧 /api/advance-state — 推进到下一状态。"""
    STATE_ADVANCE = {
        "Taizi": "Zhongshu",
        "Zhongshu": "Menxia",
        "Menxia": "Assigned",
        "Assigned": "Doing",
        "Doing": "Review",
        "Review": "Done",
    }
    try:
        task = await svc.get_task(uuid.UUID(body.taskId))
    except ValueError:
        return {"ok": False, "error": "Task not found"}

    next_state = STATE_ADVANCE.get(task.state.value)
    if not next_state:
        return {"ok": False, "error": f"Cannot advance from {task.state.value}"}

    try:
        await svc.transition_state(
            task_id=uuid.UUID(body.taskId),
            new_state=TaskState(next_state),
            agent="system",
            reason=body.comment,
        )
        return {"ok": True}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


# ── Review Action ──

class ReviewActionBody(BaseModel):
    taskId: str
    action: str  # "approve" | "reject"
    comment: str = ""


@router.post("/api/review-action")
async def review_action(body: ReviewActionBody, svc: TaskService = Depends(_get_svc)):
    """兼容旧 /api/review-action。"""
    if body.action == "approve":
        new_state = "Done"
    elif body.action == "reject":
        new_state = "Zhongshu"
    else:
        return {"ok": False, "error": f"Unknown action: {body.action}"}

    try:
        await svc.transition_state(
            task_id=uuid.UUID(body.taskId),
            new_state=TaskState(new_state),
            agent="system",
            reason=f"Review {body.action}: {body.comment}",
        )
        return {"ok": True}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


# ── Task Activity ──

@router.get("/api/task-activity/{task_id}")
async def task_activity(task_id: str, svc: TaskService = Depends(_get_svc)):
    """兼容旧 /api/task-activity/{id} — 从 flow_log + progress_log 组装活动流。"""
    try:
        task = await svc.get_task(uuid.UUID(task_id))
    except ValueError:
        return {"ok": False, "error": "Task not found"}

    d = task.to_dict()
    activity: list[dict] = []

    for entry in d.get("flow_log", []):
        activity.append({
            "kind": "transition",
            "at": entry.get("ts", ""),
            "from": entry.get("from", ""),
            "to": entry.get("to", ""),
            "agent": entry.get("agent", ""),
            "remark": entry.get("reason", ""),
        })

    for entry in d.get("progress_log", []):
        activity.append({
            "kind": "progress",
            "at": entry.get("ts", ""),
            "agent": entry.get("agent", ""),
            "text": entry.get("content", ""),
        })

    return {"ok": True, "activity": activity}


# ── Scheduler State ──

@router.get("/api/scheduler-state/{task_id}")
async def scheduler_state(task_id: str, svc: TaskService = Depends(_get_svc)):
    """兼容旧 /api/scheduler-state/{id}。"""
    try:
        task = await svc.get_task(uuid.UUID(task_id))
    except ValueError:
        return {"ok": False, "error": "Task not found"}

    d = task.to_dict()
    return {
        "ok": True,
        "scheduler": d.get("scheduler") or d.get("_scheduler", {}),
        "stalledSec": 0,
    }


# ── Skill Content ──

@router.get("/api/skill-content/{agent_id}/{skill_name}")
async def skill_content(agent_id: str, skill_name: str):
    """兼容旧 /api/skill-content/{agentId}/{skillName}。"""
    safe_name = _safe_skill_name(skill_name)
    saved_configs = _load_agent_config_json()
    cfg = _agent_entries(saved_configs).get(agent_id, {})
    candidates: list[Path] = []
    for item in cfg.get("skills", []) if isinstance(cfg, dict) else []:
        if isinstance(item, dict) and item.get("name") == skill_name and item.get("path"):
            candidates.append(Path(str(item["path"])))
    for ext in (".md", ".txt", ".js", ""):
        candidates.append(AGENTS_DIR / agent_id / "skills" / f"{safe_name}{ext}")
    candidates.append(_workspace_skill_dir(agent_id) / safe_name / "SKILL.md")

    for p in candidates:
        try:
            if p.exists() and p.is_file():
                return {
                    "ok": True,
                    "name": skill_name,
                    "agent": agent_id,
                    "content": p.read_text(encoding="utf-8"),
                    "path": str(p),
                }
        except OSError:
            continue
    return {"ok": False, "error": f"Skill '{skill_name}' not found for agent '{agent_id}'"}


# ── Stub endpoints (Priority 2 - 返回 {ok: true} 让前端不报错) ──

class SetModelBody(BaseModel):
    agentId: str
    model: str


class DispatchChannelBody(BaseModel):
    channel: str


@router.post("/api/set-model")
async def set_model(body: SetModelBody):
    saved_configs = _load_agent_config_json()
    saved_agents = _agent_entries(saved_configs)
    agent_config = saved_agents.setdefault(body.agentId, {})
    old_model = str(agent_config.get("model") or "default")
    now = datetime.now(timezone.utc).isoformat()

    agent_config["id"] = body.agentId
    agent_config["model"] = body.model
    agent_config["updated_at"] = now
    if body.model.startswith("astrbot-config:"):
        agent_config["astrbot_config_id"] = body.model.split(":", 1)[1]
        agent_config.pop("astrbot_config_name", None)
    elif body.model == "default":
        agent_config.pop("astrbot_config_id", None)
        agent_config.pop("astrbot_config_name", None)
    else:
        agent_config.pop("astrbot_config_id", None)
        agent_config["selected_model"] = body.model

    existing_agents = [item for item in saved_configs.get("agents", []) if isinstance(item, dict) and item.get("id") != body.agentId]
    existing_agents.append(agent_config)
    saved_configs["agents"] = existing_agents

    change_log = saved_configs.setdefault("_model_change_log", [])
    change_log.append({
        "at": now,
        "agentId": body.agentId,
        "oldModel": old_model,
        "newModel": body.model,
        "effective": "new_astrbot_dispatches",
    })
    saved_configs["_model_change_log"] = change_log[-MODEL_CHANGE_LOG_LIMIT:]
    _write_json(AGENT_CONFIG_PATH, saved_configs)
    return {"ok": True, "message": "模型配置已保存；新派发到 AstrBot 的任务会读取该配置。"}


@router.post("/api/set-dispatch-channel")
async def set_dispatch_channel(body: DispatchChannelBody):
    saved_configs = _load_agent_config_json()
    saved_configs["dispatchChannel"] = body.channel
    saved_configs["_dispatch_channel"] = body.channel
    saved_configs["_dispatch_channel_updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(AGENT_CONFIG_PATH, saved_configs)
    return {"ok": True, "message": "派发渠道配置已保存；实际通知发送取决于对应 channel 是否已配置。"}

class AgentWakeBody(BaseModel):
    agentId: str


@router.post("/api/agent-wake")
async def agent_wake(body: AgentWakeBody):
    """唤醒指定 agent — 通过 event bus 发送 dispatch 请求。"""
    agent_id = body.agentId
    # 检查是否有该 agent 正在处理的停滞任务，如果有则重新派发
    try:
        bus = get_event_bus()
        if bus:
            await bus.publish(
                topic=TOPIC_TASK_DISPATCH,
                trace_id=str(uuid.uuid4()),
                event_type="agent.wake",
                producer="api.compat",
                payload={
                    "agent": agent_id,
                    "message": f"Agent {agent_id} 被手动唤醒",
                },
            )
    except Exception as e:
        log.warning(f"Agent wake publish failed: {e}")

    return {"ok": True, "message": f"已发送唤醒信号给 {agent_id}"}

@router.post("/api/scheduler-scan")
async def scheduler_scan():
    return {"ok": True, "count": 0, "actions": [], "checkedAt": datetime.now(timezone.utc).isoformat()}

@router.post("/api/scheduler-retry")
async def scheduler_retry():
    return {"ok": True}

@router.post("/api/scheduler-escalate")
async def scheduler_escalate():
    return {"ok": True}

@router.post("/api/scheduler-rollback")
async def scheduler_rollback():
    return {"ok": True}


# ══════════════════════════════════════════
# Priority 3 — 辅助面板 (stubs)
# ══════════════════════════════════════════

@router.get("/api/model-change-log")
async def model_change_log():
    saved_configs = _load_agent_config_json()
    return saved_configs.get("_model_change_log", [])

@router.get("/api/officials-stats")
async def officials_stats(db: AsyncSession = Depends(get_db)):
    """官员总览 — 从数据库统计各官员任务数据。"""
    from sqlalchemy import func, case, select as sa_select
    from ..models.task import Task

    # 基础统计：每个 org 的任务完成数和活跃数
    stmt = (
        sa_select(
            Task.org,
            func.count().label("total"),
            func.sum(case((Task.state == TaskState.Done, 1), else_=0)).label("done"),
            func.sum(case(
                (Task.state.in_([TaskState.Doing, TaskState.Review, TaskState.Assigned, TaskState.Next]), 1),
                else_=0
            )).label("active"),
            func.max(Task.updated_at).label("last_active"),
        )
        .where(Task.archived == False)  # noqa: E712
        .group_by(Task.org)
    )
    result = await db.execute(stmt)
    rows = result.all()

    # 构建按 org 名的统计 map
    org_stats: dict[str, dict] = {}
    for row in rows:
        org_stats[row.org or ""] = {
            "done": int(row.done or 0),
            "active": int(row.active or 0),
            "last_active": row.last_active.isoformat() if row.last_active else "",
        }

    # 为每个官员生成统计
    officials = []
    total_done = 0
    top_official = ""
    top_done = 0

    for d in AGENT_DEFS:
        oid = d["id"]
        label = d["label"]
        # 找到该官员对应的 org 统计
        stat = org_stats.get(label, {"done": 0, "active": 0, "last_active": ""})

        done = stat["done"]
        active = stat["active"]
        total_done += done
        if done > top_done:
            top_done = done
            top_official = f"{d['emoji']} {label}"

        officials.append({
            "id": oid,
            "label": label,
            "emoji": d["emoji"],
            "role": d["role"],
            "rank": d["rank"],
            "model": "-",
            "model_short": "-",
            "tokens_in": 0,
            "tokens_out": 0,
            "cache_read": 0,
            "cache_write": 0,
            "cost_cny": 0,
            "cost_usd": 0,
            "sessions": 0,
            "messages": 0,
            "tasks_done": done,
            "tasks_active": active,
            "flow_participations": 0,
            "merit_score": done * 10,
            "merit_rank": 0,
            "last_active": stat["last_active"],
            "heartbeat": {"status": "idle", "label": "待命"},
            "participated_edicts": [],
        })

    # 按功绩排序赋排名
    officials.sort(key=lambda x: x["merit_score"], reverse=True)
    for i, o in enumerate(officials):
        o["merit_rank"] = i + 1

    return {
        "officials": officials,
        "totals": {"tasks_done": total_done, "cost_cny": 0},
        "top_official": top_official,
    }

class MorningConfigBody(BaseModel):
    categories: list[dict] = []
    keywords: list[str] = []
    custom_feeds: list[dict] = []
    wecom_webhook: str = ""
    feishu_webhook: str = ""
    enabled: bool = True


def _load_morning_config() -> dict:
    config = _read_json(MORNING_CONFIG_PATH, DEFAULT_MORNING_CONFIG)
    if not isinstance(config, dict):
        config = DEFAULT_MORNING_CONFIG
    return normalize_morning_config({**DEFAULT_MORNING_CONFIG, **config})


async def _run_morning_refresh() -> None:
    global _morning_refresh_running
    async with _morning_refresh_lock:
        _morning_refresh_running = True
        try:
            config = _load_morning_config()
            brief = await collect_morning_brief(config, DATA_DIR)
            push_results = push_morning_brief(brief, config)
            if push_results:
                log.info("Morning brief push results: %s", push_results)
            log.info("Morning brief refreshed")
        except Exception:
            log.exception("Morning brief refresh failed")
        finally:
            _morning_refresh_running = False


@router.get("/api/morning-brief")
async def morning_brief():
    brief = _read_json(MORNING_BRIEF_PATH, None)
    if isinstance(brief, dict):
        brief.setdefault("categories", {})
        brief.setdefault("enabled", True)
        brief.setdefault("message", "天下要闻已采集。")
        return brief
    return {
        "date": "",
        "generated_at": "",
        "categories": {},
        "enabled": True,
        "message": "暂无天下要闻数据，请点击立即采集。",
    }


@router.get("/api/morning-config")
async def morning_config():
    return _load_morning_config()


@router.post("/api/morning-config")
async def save_morning_config(body: MorningConfigBody):
    payload = normalize_morning_config(body.model_dump())
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    payload["message"] = "订阅配置已保存。"
    _write_json(MORNING_CONFIG_PATH, payload)
    return {"ok": True, "message": payload["message"]}


@router.post("/api/morning-brief/refresh")
async def refresh_morning(background_tasks: BackgroundTasks):
    if _morning_refresh_running or _morning_refresh_lock.locked():
        return {"ok": True, "message": "采集中，请稍候…"}
    background_tasks.add_task(_run_morning_refresh)
    return {"ok": True, "message": "采集已触发，自动检测更新中…"}


@router.get("/api/remote-skills-list")
async def remote_skills_list():
    saved_configs = _load_agent_config_json()
    remote_skills = saved_configs.get("remoteSkills")
    if not isinstance(remote_skills, list):
        remote_skills = []
    return {
        "ok": True,
        "remoteSkills": remote_skills,
        "count": len(remote_skills),
        "listedAt": datetime.now(timezone.utc).isoformat(),
    }


class AddSkillBody(BaseModel):
    agentId: str
    skillName: str
    description: str = ""
    trigger: str = ""


class RemoteSkillBody(BaseModel):
    agentId: str
    skillName: str
    sourceUrl: str = ""
    description: str = ""


class SkillRefBody(BaseModel):
    agentId: str
    skillName: str


def _write_local_skill(agent_id: str, skill_name: str, content: str) -> Path:
    safe_name = _safe_skill_name(skill_name)
    if not safe_name:
        raise ValueError("技能名称无效")
    skills_dir = _workspace_skill_dir(agent_id) / safe_name
    skills_dir.mkdir(parents=True, exist_ok=True)
    path = skills_dir / "SKILL.md"
    path.write_text(content, encoding="utf-8")
    return path


def _upsert_skill_config(agent_id: str, name: str, description: str, path: Path) -> None:
    saved_configs = _load_agent_config_json()
    saved_agents = _agent_entries(saved_configs)
    agent_config = saved_agents.setdefault(agent_id, {"id": agent_id})
    skills = [item for item in agent_config.get("skills", []) if isinstance(item, dict) and item.get("name") != name]
    skills.append({"name": name, "description": description, "path": str(path)})
    agent_config["id"] = agent_id
    agent_config["skills"] = skills
    existing_agents = [item for item in saved_configs.get("agents", []) if isinstance(item, dict) and item.get("id") != agent_id]
    existing_agents.append(agent_config)
    saved_configs["agents"] = existing_agents
    _write_json(AGENT_CONFIG_PATH, saved_configs)


@router.post("/api/add-skill")
async def add_skill(body: AddSkillBody):
    safe_name = _safe_skill_name(body.skillName)
    if not safe_name:
        return {"ok": False, "error": "技能名称无效"}
    content = "\n".join([
        f"# {safe_name}",
        "",
        body.description.strip() or "本地技能。",
        "",
        "## 触发方式",
        body.trigger.strip() or "由任务上下文判断是否使用。",
    ]).strip() + "\n"
    try:
        path = _write_local_skill(body.agentId, safe_name, content)
        _upsert_skill_config(body.agentId, safe_name, body.description, path)
    except OSError as exc:
        return {"ok": False, "error": f"写入技能失败：{exc}"}
    return {"ok": True, "message": "技能已保存到本地工作区", "skillName": safe_name, "agentId": body.agentId, "localPath": str(path)}


@router.post("/api/add-remote-skill")
async def add_remote_skill(body: RemoteSkillBody):
    safe_name = _safe_skill_name(body.skillName)
    if not safe_name:
        return {"ok": False, "error": "技能名称无效"}
    if not body.sourceUrl.startswith("https://"):
        return {"ok": False, "error": "远程技能仅允许 HTTPS 地址"}
    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
            resp = await client.get(body.sourceUrl)
            resp.raise_for_status()
            content = resp.text[:200_000]
        path = _write_local_skill(body.agentId, safe_name, content)
        _upsert_skill_config(body.agentId, safe_name, body.description, path)
    except Exception as exc:
        return {"ok": False, "error": f"导入远程技能失败：{exc}"}

    saved_configs = _load_agent_config_json()
    remote_skills = [item for item in saved_configs.get("remoteSkills", []) if isinstance(item, dict) and not (item.get("agentId") == body.agentId and item.get("skillName") == safe_name)]
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "skillName": safe_name,
        "agentId": body.agentId,
        "sourceUrl": body.sourceUrl,
        "description": body.description,
        "localPath": str(path),
        "addedAt": now,
        "lastUpdated": now,
        "status": "valid",
    }
    remote_skills.append(record)
    saved_configs["remoteSkills"] = remote_skills
    _write_json(AGENT_CONFIG_PATH, saved_configs)
    return {"ok": True, "message": "远程技能已导入本地工作区", **record}


@router.post("/api/update-remote-skill")
async def update_remote_skill(body: SkillRefBody):
    saved_configs = _load_agent_config_json()
    remote_skills = saved_configs.get("remoteSkills") if isinstance(saved_configs.get("remoteSkills"), list) else []
    target = next((item for item in remote_skills if isinstance(item, dict) and item.get("agentId") == body.agentId and item.get("skillName") == body.skillName), None)
    if not target:
        return {"ok": False, "error": "未找到远程技能记录"}
    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
            resp = await client.get(str(target.get("sourceUrl") or ""))
            resp.raise_for_status()
            content = resp.text[:200_000]
        path = _write_local_skill(body.agentId, body.skillName, content)
        target["localPath"] = str(path)
        target["lastUpdated"] = datetime.now(timezone.utc).isoformat()
        target["status"] = "valid"
        _upsert_skill_config(body.agentId, body.skillName, str(target.get("description") or ""), path)
        saved_configs["remoteSkills"] = remote_skills
        _write_json(AGENT_CONFIG_PATH, saved_configs)
    except Exception as exc:
        target["status"] = "not-found"
        _write_json(AGENT_CONFIG_PATH, saved_configs)
        return {"ok": False, "error": f"更新远程技能失败：{exc}"}
    return {"ok": True, "message": "远程技能已更新"}


@router.post("/api/remove-remote-skill")
async def remove_remote_skill(body: SkillRefBody):
    saved_configs = _load_agent_config_json()
    remote_skills = saved_configs.get("remoteSkills") if isinstance(saved_configs.get("remoteSkills"), list) else []
    saved_configs["remoteSkills"] = [item for item in remote_skills if not (isinstance(item, dict) and item.get("agentId") == body.agentId and item.get("skillName") == body.skillName)]
    saved_agents = _agent_entries(saved_configs)
    agent_config = saved_agents.get(body.agentId)
    if agent_config:
        agent_config["skills"] = [item for item in agent_config.get("skills", []) if not (isinstance(item, dict) and item.get("name") == body.skillName)]
        existing_agents = [item for item in saved_configs.get("agents", []) if isinstance(item, dict) and item.get("id") != body.agentId]
        existing_agents.append(agent_config)
        saved_configs["agents"] = existing_agents
    skill_dir = _workspace_skill_dir(body.agentId) / _safe_skill_name(body.skillName)
    skill_file = skill_dir / "SKILL.md"
    try:
        if skill_file.exists():
            skill_file.unlink()
        if skill_dir.exists() and not any(skill_dir.iterdir()):
            skill_dir.rmdir()
    except OSError as exc:
        return {"ok": False, "error": f"删除技能文件失败：{exc}"}
    _write_json(AGENT_CONFIG_PATH, saved_configs)
    return {"ok": True, "message": "技能已移除"}

# ── Court Discuss (朝堂议政) ──

import asyncio
import random

# 内存会话存储
_court_sessions: dict[str, dict] = {}

# 官员性格设定
_OFFICIAL_PERSONALITY: dict[str, dict] = {
    "taizi":    {"personality": "稳重持重，善于权衡利弊，说话斟酌，有大局观", "speaking_style": "温和而坚定，经常引用历史典故"},
    "zhongshu": {"personality": "深思熟虑，善于规划方案，注重可行性和效率", "speaking_style": "条理清晰，喜欢列举一二三"},
    "menxia":   {"personality": "严谨挑剔，善于发现漏洞和风险，不轻易放行", "speaking_style": "尖锐直接，常用反问句"},
    "shangshu": {"personality": "务实高效，关注执行细节和资源分配", "speaking_style": "简洁干练，关注落地方案"},
    "libu":     {"personality": "文雅有礼，关注制度规范和礼仪", "speaking_style": "引经据典，措辞文雅"},
    "hubu":     {"personality": "精打细算，对数字敏感，关注成本效益", "speaking_style": "喜欢用数据说话，关注预算"},
    "bingbu":   {"personality": "果断勇猛，关注安全和应急响应，雷厉风行", "speaking_style": "简洁有力，直指要害"},
    "xingbu":   {"personality": "公正严格，关注合规和法律风险", "speaking_style": "严谨细致，喜欢引用条文"},
    "gongbu":   {"personality": "创新务实，擅长技术和工程方案", "speaking_style": "务实详细，喜欢画蓝图"},
    "libu_hr":  {"personality": "善于识人用人，关注团队配置和人员发展", "speaking_style": "温和中肯，善于调和各方"},
    "zaochao":  {"personality": "消息灵通，关注时事和舆论动向", "speaking_style": "语速快，信息量大"},
}

# 命运骰子事件
_FATE_EVENTS = [
    "边疆急报：北方蛮族集结兵马，似有南下之意",
    "天降祥瑞：五彩祥云现于长安上空",
    "户部急呈：国库银两出现大量亏空",
    "民间传言：百姓对新政议论纷纷",
    "外国使团：西域诸国遣使来朝，请求通商",
    "天象异常：钦天监报告近日星象有变",
    "黄河决堤：沿岸数州告急，请求赈灾",
    "科举放榜：今年进士科人才济济",
    "宫廷宴会：太后寿辰将至，需筹备庆典",
    "瘟疫传闻：南方数州出现疫病征兆",
    "商路畅通：丝绸之路贸易额创新高",
    "朝中密报：有官员私下结党营私",
    "丰年吉兆：今年各地粮食丰收",
    "边境冲突：守军与邻国巡逻队发生摩擦",
    "天降大雨：连日暴雨，多地农田受灾",
    "发明献礼：工部呈上新式水利装置",
    "民间疾苦：多地百姓反映赋税过重",
    "国威大振：水师在东海演习威震四方",
    "奇才出现：一少年才俊献上万言书",
    "朝廷喜事：公主即将下嫁和亲",
]

_FATE_EMOTIONS = ["震惊", "紧张", "兴奋", "忧虑", "议论纷纷", "骚动"]


def _get_official_meta(official_id: str) -> dict:
    """获取官员元信息。"""
    for d in AGENT_DEFS:
        if d["id"] == official_id:
            return d
    return {"id": official_id, "label": official_id, "emoji": "👤", "role": "官员", "rank": "未知"}


def _build_court_prompt(session: dict, official_id: str, extra: str = "") -> str:
    """构建朝议 prompt，注入角色设定和讨论上下文。"""
    meta = _get_official_meta(official_id)
    personality = _OFFICIAL_PERSONALITY.get(official_id, {})
    topic = session["topic"]
    officials = session["officials"]
    history = session.get("messages", [])[-20:]  # 最近 20 条消息作为上下文

    # 构建朝堂在场人员
    present = "、".join(
        f"{_get_official_meta(o['id'])['label']}（{_get_official_meta(o['id'])['role']}）"
        for o in officials
    )

    prompt = f"""# 朝堂议政 · 角色扮演

你正在参加一场朝堂议政。请严格扮演你的角色发言。

## 你的角色
- **身份**: {meta['label']}（{meta['role']}），{meta.get('rank', '')}
- **性格**: {personality.get('personality', '稳重有主见')}
- **说话风格**: {personality.get('speaking_style', '得体大方')}

## 议题
{topic}

## 在场官员
{present}

## 讨论记录（最近发言）
"""
    for msg in history:
        if msg.get("type") == "official":
            prompt += f"- {msg.get('official_name', '某官')}：{msg.get('content', '')}\n"
        elif msg.get("type") == "emperor":
            prompt += f"- 👑 皇上：{msg.get('content', '')}\n"
        elif msg.get("type") == "decree":
            prompt += f"- ⚡ 天命：{msg.get('content', '')}\n"
        elif msg.get("type") == "scene_note":
            prompt += f"- 📢 {msg.get('content', '')}\n"

    if extra:
        prompt += f"\n## 当前情境\n{extra}\n"

    prompt += """
## 要求
请以你的角色身份发表观点，要求：
1. 紧扣议题，不要跑题
2. 体现你的角色性格和说话风格
3. 发言 50-150 字为宜
4. 只输出你的发言内容，不要加引号、括号或角色名前缀
5. 如果有情绪倾向，请在末尾用 [情绪:xxx] 标注，可选：neutral/confident/worried/angry/thinking/amused/happy
"""
    return prompt


def _parse_emotion(text: str) -> tuple[str, str]:
    """从回复中解析情绪标注 [情绪:xxx]。"""
    import re
    m = re.search(r'\[情绪:(\w+)\]\s*$', text)
    if m:
        emotion = m.group(1)
        content = text[:m.start()].strip()
        return content, emotion
    return text, "neutral"


async def _call_llm(prompt: str) -> str:
    """调用 LLM 生成回复。优先级：LLM 直调 > AstrBot adapter > 模拟回复。"""
    import httpx

    settings = get_settings()
    api_url = settings.llm_api_url
    api_key = settings.llm_api_key
    model = settings.llm_model

    # 优先：LLM 直调
    if api_url and api_key:
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是一个角色扮演AI，请严格按照给定角色和场景发言。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.8,
            "max_tokens": 300,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(api_url, json=body, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                log.error(f"LLM API error {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            log.warning(f"LLM direct call failed: {e}")

    # 回退：AstrBot adapter
    try:
        adapter = create_adapter()
        result = await adapter.invoke(
            agent="zhongshu",
            message=prompt,
            task_id=f"court_llm_{uuid.uuid4().hex[:6]}",
            trace_id=f"court_llm",
        )
        output = result.get("stdout", "").strip()
        if output:
            return output
    except Exception as e:
        log.warning(f"AstrBot fallback failed: {e}")

    # 最终回退：模拟回复（从 prompt 中提取角色名）
    return ""  # 由 _call_official 处理空值


# 模拟回复模板（LLM 不可用时的最终回退）
_SIMULATED_RESPONSES: dict[str, list[str]] = {
    "taizi": [
        "本宫以为此事当从长计议，不可操之过急。",
        "父皇所虑极是，容儿臣细细思量后呈上方案。",
        "此事牵涉甚广，需各方协同方能周全。",
    ],
    "zhongshu": [
        "臣以为当先拟定章程，再交由各部门商议执行。",
        "依臣之见，此事可分为三步推进：其一摸清情况，其二制定方案，其三分头落实。",
        "容臣与同僚商议后，明日早朝呈上详细方案。",
    ],
    "menxia": [
        "此事虽有其理，但其中尚有几处漏洞需要斟酌。",
        "臣仔细审核后认为，方案大体可行，但需补充应急之策。",
        "容臣再行复核，确保万无一失后方可放行。",
    ],
    "shangshu": [
        "臣这就安排各部着手执行，定不负圣望。",
        "此事需户部配合拨款、工部负责实施，臣即刻协调。",
        "已部署完毕，预计三日内可见初步成效。",
    ],
    "libu": [
        "礼制不可废，此事须按规制办理，方显朝廷威仪。",
        "臣以为当遵循旧例，同时可酌情变通以适应时局。",
        "礼仪之邦，当以此事为契机，彰显我朝文治之盛。",
    ],
    "hubu": [
        "国库虽有盈余，但仍需精打细算，不可铺张。",
        "臣初步估算，此项开支约需白银十万两，需从节流项下调拨。",
        "账目清楚，每一分银子都要花在刀刃上。",
    ],
    "bingbu": [
        "兵贵神速！此事若要行，当雷厉风行不可拖延。",
        "臣已命边关加强戒备，同时加紧操练兵马。",
        "安全问题不可小觑，须未雨绸缪方为上策。",
    ],
    "xingbu": [
        "依律而言，此事尚需斟酌法理，不可贸然行事。",
        "臣会严格按律法审核，确保不违祖制。",
        "法度乃立国之本，任何举措都须在法理框架内施行。",
    ],
    "gongbu": [
        "臣已着手绘制蓝图，此项工程可在月内完工。",
        "技术上完全可行，关键在于选材与工期安排。",
        "臣已拟定三套方案，各有优劣，请圣上定夺。",
    ],
    "libu_hr": [
        "人才乃立国之本，此事需选贤任能方能成事。",
        "臣以为当广开仕路，不拘一格降人才。",
        "吏治清明则天下安，臣定当严格考核，择优而用。",
    ],
    "zaochao": [
        "据臣最新掌握的情报，各地方对此事反响不一。",
        "坊间议论纷纷，民间对此多有期待。",
        "臣已将各方消息整理完毕，供各位大人参考。",
    ],
}


async def _call_official(session: dict, official_id: str, extra: str = "") -> dict:
    """调用 LLM 为单个官员生成回复。"""
    prompt = _build_court_prompt(session, official_id, extra)

    output = await _call_llm(prompt)
    if not output:
        # LLM 不可用，使用模拟回复
        pool = _SIMULATED_RESPONSES.get(official_id, ["（沉默不语）"])
        output = random.choice(pool)

    content, emotion = _parse_emotion(output)
    meta = _get_official_meta(official_id)

    return {
        "official_id": official_id,
        "name": f"{meta['emoji']} {meta['label']}",
        "content": content,
        "emotion": emotion,
    }


class CourtStartRequest(BaseModel):
    topic: str
    officials: list[str]
    taskId: str | None = None


class CourtAdvanceRequest(BaseModel):
    sessionId: str
    userMessage: str | None = None
    decree: str | None = None


class CourtSessionRequest(BaseModel):
    sessionId: str


@router.post("/api/court-discuss/start")
async def court_discuss_start(req: CourtStartRequest):
    """启动朝堂议政会话。"""
    session_id = f"court_{uuid.uuid4().hex[:12]}"
    officials_info = []
    for oid in req.officials:
        meta = _get_official_meta(oid)
        personality = _OFFICIAL_PERSONALITY.get(oid, {})
        officials_info.append({
            "id": oid,
            "name": f"{meta['emoji']} {meta['label']}",
            "emoji": meta["emoji"],
            "role": meta["role"],
            "personality": personality.get("personality", "稳重有主见"),
            "speaking_style": personality.get("speaking_style", "得体大方"),
        })

    session = {
        "session_id": session_id,
        "topic": req.topic,
        "officials": officials_info,
        "official_ids": req.officials,
        "messages": [],
        "round": 0,
        "phase": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _court_sessions[session_id] = session

    # start 立即返回空会话，第一轮由 advance 触发
    return {
        "ok": True,
        "session_id": session_id,
        "topic": req.topic,
        "officials": officials_info,
        "messages": [],
        "round": 0,
        "phase": "active",
        "new_messages": [],
        "scene_note": f"📖 朝堂议政开始，议题：{req.topic}",
        "total_messages": 0,
    }


@router.post("/api/court-discuss/advance")
async def court_discuss_advance(req: CourtAdvanceRequest):
    """推进朝堂议政到下一轮。"""
    session = _court_sessions.get(req.sessionId)
    if not session:
        return {"ok": False, "error": "会话不存在或已结束"}

    if session["phase"] != "active":
        return {"ok": False, "error": "会话已结束，无法继续讨论"}

    # 记录用户消息
    extra_parts = []
    if req.userMessage:
        session["messages"].append({
            "type": "emperor",
            "content": req.userMessage,
        })
        extra_parts.append(f"皇上刚刚发言：「{req.userMessage}」，请各位大臣回应。")

    if req.decree:
        session["messages"].append({
            "type": "decree",
            "content": req.decree,
        })
        extra_parts.append(f"天命降临：「{req.decree}」，所有人必须遵从！")

    extra = "\n".join(extra_parts) if extra_parts else "请继续发表观点或回应其他大臣的发言。"

    # 下一轮发言：让所有官员回复
    new_messages = []
    tasks = []
    for oid in session["official_ids"]:
        tasks.append(_call_official(session, oid, extra))
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in results:
        if isinstance(r, Exception):
            log.warning(f"Court discuss advance error: {r}")
            continue
        new_messages.append(r)
        session["messages"].append({
            "type": "official",
            "official_id": r["official_id"],
            "official_name": r["name"],
            "content": r["content"],
            "emotion": r.get("emotion", "neutral"),
        })

    session["round"] = session.get("round", 0) + 1

    # 偶尔添加场景注解
    scene_note = None
    if random.random() < 0.3:
        scene_note = random.choice([
            "大殿内气氛热烈，众臣各抒己见",
            "朝堂上一时鸦雀无声，众人陷入沉思",
            "有大臣激动地挥舞着手中的笏板",
            "窗外传来更鼓声，时间不知不觉过去了",
            "几位大臣互相交换了眼神",
        ])

    return {
        "ok": True,
        "session_id": req.sessionId,
        "round": session["round"],
        "new_messages": new_messages,
        "scene_note": scene_note,
        "total_messages": len(session["messages"]),
    }


@router.post("/api/court-discuss/conclude")
async def court_discuss_conclude(req: CourtSessionRequest):
    """结束朝堂议政，生成总结。"""
    session = _court_sessions.get(req.sessionId)
    if not session:
        return {"ok": False, "error": "会话不存在"}

    session["phase"] = "concluded"

    # 使用 AI 生成总结
    summary = ""
    try:
        history = session.get("messages", [])
        history_text = "\n".join(
            f"- {m.get('official_name', m.get('type', ''))}：{m.get('content', '')}"
            for m in history[-15:]
        )
        prompt = f"""请用 3-5 句话总结以下朝堂议政的讨论结果，包括主要观点、分歧和共识：

议题：{session['topic']}

讨论记录：
{history_text}

请直接输出总结，不要加标题或前缀。"""

        summary = await _call_llm(prompt)
    except Exception as e:
        log.warning(f"Court discuss summary failed: {e}")
    if not summary:
        msg_count = len(session.get("messages", []))
        summary = f"本次朝议共 {session.get('round', 0)} 轮讨论，{msg_count} 条发言。"

    return {"ok": True, "summary": summary}


@router.post("/api/court-discuss/destroy")
async def court_discuss_destroy(req: CourtSessionRequest):
    """销毁朝堂议政会话。"""
    session = _court_sessions.pop(req.sessionId, None)
    if session:
        log.info(f"Court discuss session {req.sessionId} destroyed")
    return {"ok": True}


@router.get("/api/court-discuss/fate")
async def court_discuss_fate():
    """返回随机命运事件。"""
    event = random.choice(_FATE_EVENTS)
    return {"ok": True, "event": event}
