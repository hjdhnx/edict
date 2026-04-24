"""OpenClaw Adapter — 通过 CLI 子进程调用 OpenClaw Agent。"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import pathlib
import subprocess
import tempfile

from ..config import get_settings
from .base import AgentAdapter

log = logging.getLogger("edict.adapter.openclaw")


def _resolve_agents_dir() -> pathlib.Path:
    """定位 agents/ 目录。"""
    settings = get_settings()
    if settings.openclaw_project_dir:
        return pathlib.Path(settings.openclaw_project_dir) / "agents"
    return pathlib.Path(__file__).resolve().parents[4] / "agents"


def _build_soul_context(agent_id: str) -> str:
    """拼装三层 prompt 层级：GLOBAL.md -> group/*.md -> {agent}/SOUL.md。"""
    agents_dir = _resolve_agents_dir()

    # Agent 分组映射
    group_map = {
        "taizi": "sansheng",
        "zhongshu": "sansheng",
        "menxia": "sansheng",
        "shangshu": "sansheng",
        "hubu": "liubu",
        "libu": "liubu",
        "bingbu": "liubu",
        "xingbu": "liubu",
        "gongbu": "liubu",
        "libu_hr": "liubu",
        "zaochao": None,
    }

    parts = []

    global_md = agents_dir / "GLOBAL.md"
    if global_md.exists():
        parts.append(global_md.read_text(encoding="utf-8"))

    group = group_map.get(agent_id)
    if group:
        group_md = agents_dir / "groups" / f"{group}.md"
        if group_md.exists():
            parts.append(group_md.read_text(encoding="utf-8"))

    soul_md = agents_dir / agent_id / "SOUL.md"
    if soul_md.exists():
        parts.append(soul_md.read_text(encoding="utf-8"))

    return "\n---\n".join(parts) if parts else ""


class OpenClawAdapter(AgentAdapter):
    """OpenClaw CLI 适配器 — 通过子进程调用 openclaw agent 命令。"""

    async def invoke(
        self,
        agent: str,
        message: str,
        task_id: str,
        trace_id: str,
        payload: dict | None = None,
    ) -> dict:
        """异步调用 OpenClaw CLI — 在线程池中执行，带富上下文注入。"""
        settings = get_settings()
        cmd = [
            settings.openclaw_bin,
            "agent",
            "--agent", agent,
            "-m", message,
        ]

        env = os.environ.copy()
        env["EDICT_TASK_ID"] = task_id
        env["EDICT_TRACE_ID"] = trace_id
        env["EDICT_API_URL"] = f"http://localhost:{settings.port}"

        # 注入额外上下文环境变量
        if payload:
            env["EDICT_TASK_TITLE"] = payload.get("title", "")
            env["EDICT_TASK_STATE"] = payload.get("state", "")
            env["EDICT_TASK_ORG"] = payload.get("org", "")
            env["EDICT_TASK_PRIORITY"] = payload.get("priority", "中")
            tags = payload.get("tags", [])
            if tags:
                env["EDICT_TASK_TAGS"] = ",".join(str(t) for t in tags)

        # 写入临时上下文文件（大型上下文通过文件传递，避免命令行参数过长）
        context_file = None
        if payload:
            context_data = {
                "task_id": task_id,
                "trace_id": trace_id,
                "title": payload.get("title", ""),
                "description": payload.get("description", ""),
                "state": payload.get("state", ""),
                "org": payload.get("org", ""),
                "priority": payload.get("priority", "中"),
                "tags": payload.get("tags", []),
                "todos": payload.get("todos", []),
                "flow_log": payload.get("flow_log", [])[-10:],
                "progress_log": payload.get("progress_log", [])[-5:],
                "block": payload.get("block", ""),
                "meta": payload.get("meta", {}),
            }
            try:
                fd, context_file = tempfile.mkstemp(
                    suffix=".json", prefix=f"edict_ctx_{task_id}_"
                )
                with os.fdopen(fd, "w") as f:
                    json.dump(context_data, f, ensure_ascii=False, indent=2)
                env["EDICT_CONTEXT_FILE"] = context_file
            except Exception as e:
                log.warning(f"Failed to write context file for {task_id}: {e}")

        log.debug(f"Executing: {' '.join(cmd)}")

        timeout = settings.dispatch_timeout_sec

        def _run():
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=env,
                    cwd=settings.openclaw_project_dir or None,
                )
                return {
                    "returncode": proc.returncode,
                    "stdout": proc.stdout[-5000:] if proc.stdout else "",
                    "stderr": proc.stderr[-2000:] if proc.stderr else "",
                }
            except subprocess.TimeoutExpired:
                return {"returncode": -1, "stdout": "", "stderr": f"TIMEOUT after {timeout}s"}
            except FileNotFoundError:
                return {
                    "returncode": -1,
                    "stdout": "",
                    "stderr": "openclaw command not found",
                }
            finally:
                if context_file:
                    try:
                        os.unlink(context_file)
                    except OSError:
                        pass

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _run)
