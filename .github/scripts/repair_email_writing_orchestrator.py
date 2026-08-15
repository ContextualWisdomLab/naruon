"""Apply the one-shot, test-first repair for the email-writing orchestrator."""

from pathlib import Path


def _replace_once(path: Path, old: str, new: str, *, label: str) -> None:
    """Replace one exact source fragment or fail closed when the base moved."""
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{label} anchor count changed: {text.count(old)}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _repair_client() -> None:
    """Bound response work and bind returned evidence to the requested mode."""
    path = Path("backend/services/contextual_orchestrator_client.py")
    _replace_once(
        path,
        """_MAX_MESSAGE_COUNT = 64
_MAX_MESSAGE_CHARS = 200_000
_MAX_TOTAL_MESSAGE_CHARS = 1_000_000
_MAX_SAFE_INTEGER = 2**53 - 1
""",
        """_MAX_MESSAGE_COUNT = 64
_MAX_MESSAGE_CHARS = 200_000
_MAX_TOTAL_MESSAGE_CHARS = 1_000_000
_MAX_JSON_DEPTH = 32
_MAX_JSON_NODES = 100_000
_MAX_TRACE_STEPS = 64
_MAX_SAFE_INTEGER = 2**53 - 1
""",
        label="client constants",
    )
    _replace_once(
        path,
        """    return value


class ContextualOrchestratorClient:
""",
        """    return value


def _validate_json_structure(value: Any) -> None:
    \"\"\"Reject response trees whose parsing work exceeds fixed limits.\"\"\"
    pending: list[tuple[Any, int]] = [(value, 1)]
    observed_nodes = 0
    while pending:
        current, depth = pending.pop()
        observed_nodes += 1
        if depth > _MAX_JSON_DEPTH or observed_nodes > _MAX_JSON_NODES:
            raise ContextualOrchestratorError(
                \"orchestrator_malformed_response\"
            )
        if isinstance(current, dict):
            pending.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            pending.extend((item, depth + 1) for item in current)
        elif isinstance(current, str) and _contains_surrogate(current):
            raise ContextualOrchestratorError(
                \"orchestrator_malformed_response\"
            )


class ContextualOrchestratorClient:
""",
        label="JSON structure helper",
    )
    _replace_once(
        path,
        """                    completion = await self._send_once(
                        client,
                        endpoint.normalized_url + _CHAT_COMPLETIONS_PATH,
                        headers,
                        payload,
                    )
""",
        """                    completion = await self._send_once(
                        client,
                        endpoint.normalized_url + _CHAT_COMPLETIONS_PATH,
                        headers,
                        payload,
                    )
                    if completion.mode != mode:
                        raise ContextualOrchestratorError(
                            \"orchestrator_malformed_response\"
                        )
""",
        label="response mode binding",
    )
    _replace_once(
        path,
        """        if not isinstance(value, dict):
            raise ContextualOrchestratorError(\"orchestrator_malformed_response\")
        return value
""",
        """        if not isinstance(value, dict):
            raise ContextualOrchestratorError(\"orchestrator_malformed_response\")
        _validate_json_structure(value)
        return value
""",
        label="strict JSON validation",
    )
    _replace_once(
        path,
        """        if not isinstance(raw_trace, list):
            raise ContextualOrchestratorError(\"orchestrator_malformed_response\")
""",
        """        if (
            not isinstance(raw_trace, list)
            or len(raw_trace) > _MAX_TRACE_STEPS
        ):
            raise ContextualOrchestratorError(\"orchestrator_malformed_response\")
""",
        label="trace cardinality",
    )


def _repair_port() -> None:
    """Make Judge submission and cancellation deterministic during shutdown."""
    path = Path("backend/services/email_writing_orchestrator_port.py")
    text = path.read_text(encoding="utf-8")
    start = text.index("    async def run_judge(")
    end = text.index("    async def aclose(", start)
    method = '''    async def run_judge(
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

'''
    path.write_text(text[:start] + method + text[end:], encoding="utf-8")


def _repair_config_api() -> None:
    """Reject validator output that is not a canonical HTTPS origin."""
    path = Path("backend/api/tenant_config.py")
    _replace_once(
        path,
        """import logging
from typing import Optional
""",
        """import logging
from typing import Optional
from urllib.parse import urlsplit
""",
        label="tenant config imports",
    )
    _replace_once(
        path,
        """    return None if validated is None else validated.normalized_url
""",
        """    if validated is None:
        return None
    parsed = urlsplit(validated.normalized_url)
    if (
        parsed.scheme.lower() != \"https\"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {\"\", \"/\"}
    ):
        raise HTTPException(
            status_code=400,
            detail=_EMAIL_WRITING_ORCHESTRATOR_INVALID,
        )
    return validated.normalized_url
""",
        label="tenant config origin validation",
    )


def main() -> None:
    """Apply all root-cause repairs against the exact expected source shape."""
    _repair_client()
    _repair_port()
    _repair_config_api()


if __name__ == "__main__":
    main()
