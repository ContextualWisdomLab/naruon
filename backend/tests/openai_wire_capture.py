"""Shared helper for capturing the real OpenAI SDK request body at the wire.

Patching ``AsyncOpenAI`` itself (as most tests in this suite do) proves only
that production code passes the right arguments to the SDK -- it never runs
the SDK's own request-construction logic, so a test built that way can stay
green while the SDK's actual request path drifts (Devin Review, naruon#1529:
"wire coverage stops before transport"). ``CapturingTransport`` patches one
level lower, at ``httpx``'s transport boundary, so the genuine
``AsyncOpenAI`` client and all its internal logic run for real; only the
actual TCP/network send is replaced.
"""

from __future__ import annotations

import json
from typing import Any

import httpx


class CapturingTransport(httpx.AsyncBaseTransport):
    """An httpx transport that records the outgoing request instead of sending it."""

    def __init__(self, response_content: dict[str, Any]) -> None:
        """Store the fixed response body to return for every captured request."""
        self.captured_request: httpx.Request | None = None
        self.captured_body: dict[str, Any] | None = None
        self._response_content = response_content

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Record the request and its JSON body, then return the fixed response."""
        self.captured_request = request
        self.captured_body = json.loads(request.content)
        return httpx.Response(200, json=self._response_content, request=request)


def chat_completion_response(content: str) -> dict[str, Any]:
    """Return a minimal valid OpenAI chat-completion response body for ``content``."""
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-test",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
    }
