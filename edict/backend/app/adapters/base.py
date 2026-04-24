"""Agent Runtime Adapter 基类 — 所有 agent 运行时适配器的统一接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod


class AgentAdapter(ABC):
    """Agent 运行时适配器抽象基类。

    所有适配器（OpenClaw、AstrBot 等）必须实现 invoke 方法，
    返回统一格式的结果字典，供 DispatchWorker 无差别消费。
    """

    @abstractmethod
    async def invoke(
        self,
        agent: str,
        message: str,
        task_id: str,
        trace_id: str,
        payload: dict | None = None,
    ) -> dict:
        """调用 Agent 运行时执行任务。

        Args:
            agent: Agent 标识（如 "taizi", "hubu"）
            message: 富上下文消息（含任务信息、记忆、技能、提醒）
            task_id: 任务 UUID
            trace_id: 追踪 ID
            payload: 原始 dispatch 事件 payload

        Returns:
            统一结果字典:
            {
                "returncode": int,   # 0=成功, 非0=失败
                "stdout": str,       # Agent 标准输出
                "stderr": str,       # 错误输出（空串表示无错误）
            }
        """
        ...
