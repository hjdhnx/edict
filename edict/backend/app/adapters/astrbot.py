"""AstrBot Adapter — 通过 HTTP API 调用 AstrBot Agent。"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import httpx

from ..config import get_settings
from .base import AgentAdapter

log = logging.getLogger("edict.adapter.astrbot")


def _resolve_agents_dir():
    """延迟导入以避免循环依赖。"""
    from .openclaw import _resolve_agents_dir
    return _resolve_agents_dir()


def _build_soul_context(agent_id: str) -> str:
    """延迟导入以复用 OpenClaw 适配器的 SOUL.md 加载逻辑。"""
    from .openclaw import _build_soul_context
    return _build_soul_context(agent_id)


def _resolve_project_root() -> Path:
    here = Path(__file__).resolve()
    candidates = [Path.cwd(), *here.parents]
    for candidate in candidates:
        if (candidate / "data").exists() or (candidate / "agents").exists():
            return candidate
    return Path.cwd()


def _load_agent_runtime_config(agent_id: str) -> dict:
    path = _resolve_project_root() / "data" / "agent_config.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    for item in data.get("agents", []):
        if isinstance(item, dict) and item.get("id") == agent_id:
            return item
    legacy = data.get(agent_id)
    return legacy if isinstance(legacy, dict) else {}


class AstrBotAdapter(AgentAdapter):
    """AstrBot HTTP API 适配器。

    通过 POST /api/v1/chat 发送消息，收集 SSE 流式响应。
    每个 edict agent 映射到独立的 AstrBot session（edict_{agent}）。
    角色设定通过消息上下文注入，无需在 AstrBot 预配 persona。
    """

    def __init__(self):
        settings = get_settings()
        self._base_url = settings.astrbot_api_url.rstrip("/")
        self._api_key = settings.astrbot_api_key
        self._timeout = settings.astrbot_timeout_sec
        self._config_id = settings.astrbot_config_id.strip()
        self._config_name = settings.astrbot_config_name.strip()

    async def invoke(
        self,
        agent: str,
        message: str,
        task_id: str,
        trace_id: str,
        payload: dict | None = None,
    ) -> dict:
        """调用 AstrBot HTTP API 执行 Agent 任务。"""
        # 注入 SOUL.md 角色设定到消息头部
        soul_context = _build_soul_context(agent)
        if soul_context:
            message = f"# 角色设定\n{soul_context}\n\n---\n\n# 任务\n{message}"

        # 每个任务使用独立 session，避免上下文积累导致越来越慢
        session_id = f"edict_{agent}_{task_id[:8]}"
        url = f"{self._base_url}/api/v1/chat"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        # 不使用流式 — AstrBot 心跳会重置 httpx read timeout 导致永不超时
        body = {
            "username": f"edict_agent_{agent}",
            "session_id": session_id,
            "message": message,
            "enable_streaming": False,
        }
        agent_config = _load_agent_runtime_config(agent)
        config_id = str(agent_config.get("astrbot_config_id") or self._config_id).strip()
        config_name = str(agent_config.get("astrbot_config_name") or self._config_name).strip()
        selected_model = str(agent_config.get("selected_model") or "").strip()
        selected_provider = str(agent_config.get("selected_provider") or "").strip()
        model_value = str(agent_config.get("model") or "").strip()
        if model_value.startswith("astrbot-config:"):
            config_id = model_value.split(":", 1)[1]
            config_name = ""
        elif model_value and model_value != "default" and not selected_model:
            selected_model = model_value

        if config_id:
            body["config_id"] = config_id
        elif config_name:
            body["config_name"] = config_name
        if selected_provider:
            body["selected_provider"] = selected_provider
        if selected_model:
            body["selected_model"] = selected_model

        config_hint = config_id or config_name or selected_model or "default"
        log.info(
            f"Calling AstrBot: agent={agent}, session={session_id}, "
            f"task={task_id}, config={config_hint}, msg_len={len(message)}"
        )

        try:
            return await self._call_with_sse(url, headers, body, task_id, agent)
        except httpx.TimeoutException:
            log.warning(f"AstrBot timeout for task {task_id}")
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": f"TIMEOUT after {self._timeout}s (AstrBot)",
            }
        except httpx.ConnectError as e:
            log.error(f"AstrBot connection failed: {e}")
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": f"AstrBot connection refused: {e}",
            }
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            log.error(f"AstrBot HTTP {status}: {e.response.text[:500]}")
            # 401/403 → 不可重试; 5xx → 可重试
            return {
                "returncode": 1 if status >= 500 else -1,
                "stdout": "",
                "stderr": f"AstrBot HTTP {status}: {e.response.text[:500]}",
            }
        except Exception as e:
            log.error(f"AstrBot call failed: {e}", exc_info=True)
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": f"AstrBot error: {e}",
            }

    async def _call_with_sse(
        self,
        url: str,
        headers: dict,
        body: dict,
        task_id: str,
        agent: str,
    ) -> dict:
        """发送请求并收集 SSE 流式响应。

        AstrBot SSE 协议:
        - data: {"type": "plain", "data": "文本片段"}  — 内容（流式逐字/非流式全文）
        - data: {"type": "complete", "data": "完整文本"} — 最终完整响应
        - data: {"type": "end", "data": ""}             — 流结束信号
        - data: {"type": "session_id", "data": null}    — 会话开始
        - : heartbeat                                   — 心跳保活（SSE 注释）
        """
        collected_chunks = []
        complete_text = ""

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST", url, json=body, headers=headers
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    raise httpx.HTTPStatusError(
                        f"HTTP {response.status_code}",
                        request=response.request,
                        response=response,
                    )

                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    # SSE 注释（如 ": heartbeat"），跳过
                    if line.startswith(":"):
                        continue
                    # SSE 数据行
                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            evt = json.loads(data_str)
                        except json.JSONDecodeError:
                            collected_chunks.append(data_str)
                            continue

                        evt_type = evt.get("type", "")

                        # 结束信号
                        if evt_type == "end":
                            break

                        # 内容片段 — data 可能是字符串（plain）或 dict（其他）
                        if evt_type == "plain":
                            chunk = evt.get("data", "")
                            if isinstance(chunk, str) and chunk:
                                collected_chunks.append(chunk)
                        elif evt_type == "complete":
                            text = evt.get("data", "")
                            if isinstance(text, str) and text:
                                complete_text = text

        # 优先使用 complete 全文，否则拼接流式片段
        full_output = complete_text or "".join(collected_chunks)
        if not full_output:
            log.warning(f"AstrBot returned empty output for task {task_id}")

        log.info(
            f"AstrBot response: agent={agent}, task={task_id}, "
            f"output_len={len(full_output)}"
        )
        return {
            "returncode": 0,
            "stdout": full_output[-5000:] if full_output else "",
            "stderr": "",
        }
