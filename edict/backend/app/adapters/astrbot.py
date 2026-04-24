"""AstrBot Adapter — 通过 HTTP API 调用 AstrBot Agent。"""

from __future__ import annotations

import asyncio
import json
import logging

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

        log.info(
            f"Calling AstrBot: agent={agent}, session={session_id}, "
            f"task={task_id}, msg_len={len(message)}"
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
