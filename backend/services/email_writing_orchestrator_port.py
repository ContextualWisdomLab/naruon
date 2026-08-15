"""Concurrency-bounded port for Naruon's email-writing model workflow.

Candidate generation remains async. The independent Judge may expose a
synchronous API, so the port provides a capacity-limited worker lane that never
runs Judge computation on the FastAPI event-loop thread. Cancellation waits for
the submitted worker to settle before returning capacity, preventing hidden
oversubscription.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
import threading
from typing import ParamSpec, TypeVar

from services.contextual_orchestrator_client import (
    ChatMessage,
    ContextualOrchestratorClient,
    OrchestrationMode,
)

P = ParamSpec("P")
R = TypeVar("R")


class EmailWritingOrchestratorPort:
    """Candidate and Judge orchestration boundary for email-writing review."""

    def __init__(
        self,
        client: ContextualOrchestratorClient,
        *,
        judge_capacity: int = 2,
    ) -> None:
        """Create a port with a fixed-size Judge worker lane."""
        if judge_capacity <= 0 or judge_capacity > 32:
            raise ValueError("judge_capacity must be between 1 and 32")
        self._client = client
        self._judge_capacity = judge_capacity
        self._judge_semaphore = asyncio.Semaphore(judge_capacity)
        self._judge_executor = ThreadPoolExecutor(
            max_workers=judge_capacity,
            thread_name_prefix="email_writing_judge",
        )
        self._state_lock = threading.Lock()
        self._closed = False

    async def complete_candidate(
        self,
        messages: Sequence[ChatMessage],
        *,
        mode: OrchestrationMode,
    ) -> dict[str, object]:
        """Run async candidate generation through contextual-orchestrator."""
        self._assert_open()
        completion = await self._client.complete(messages, mode=mode)
        return completion.as_dict()

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        mode: OrchestrationMode,
    ) -> dict[str, object]:
        """Run a completion from synchronous Judge-compatible code."""
        self._assert_open()
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError("sync_completion_on_event_loop")
        completion = asyncio.run(self._client.complete(messages, mode=mode))
        return completion.as_dict()

    async def run_judge(
        self,
        operation: Callable[P, R],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> R:
        """Run one synchronous Judge operation in the bounded worker lane."""
        self._assert_judge_lane_open()
        await self._judge_semaphore.acquire()
        try:
            loop = asyncio.get_running_loop()
            with self._state_lock:
                if self._closed:
                    raise RuntimeError("judge_lane_closed")
                future = loop.run_in_executor(
                    self._judge_executor,
                    lambda: operation(*args, **kwargs),
                )
            try:
                return await asyncio.shield(future)
            except asyncio.CancelledError:
                try:
                    await asyncio.shield(future)
                except Exception:
                    pass
                raise
        finally:
            self._judge_semaphore.release()

    async def aclose(self) -> None:
        """Close candidate transport and settle the Judge worker lane."""
        with self._state_lock:
            if self._closed:
                return
            self._closed = True
        await self._client.aclose()
        await asyncio.to_thread(
            self._judge_executor.shutdown,
            True,
            cancel_futures=False,
        )

    def _assert_open(self) -> None:
        """Reject candidate work after closure."""
        with self._state_lock:
            if self._closed:
                raise RuntimeError("orchestrator_port_closed")

    def _assert_judge_lane_open(self) -> None:
        """Reject Judge work after closure with a stable lane code."""
        with self._state_lock:
            if self._closed:
                raise RuntimeError("judge_lane_closed")
