#!/usr/bin/env python3
"""Create the test-first adaptive contextual-orchestrator KG extraction patch."""

from __future__ import annotations

import sys
from pathlib import Path

SOURCE_PATH = Path("backend/services/project_graph/llm_extractor.py")
REGISTRY_PATH = Path("backend/services/project_graph/extractor_registry.py")
TEST_PATH = Path("backend/tests/test_project_graph_orchestrator_transport.py")
CHANGELOG_PATH = Path("CHANGELOG.md")
ADR_PATH = Path("docs/adr/0100-adaptive-contextual-orchestrator-default.md")

TEST_CONTENT = '''"""Transport contracts for adaptive contextual-orchestrator extraction."""

from __future__ import annotations

import types
from unittest.mock import AsyncMock

import pytest

import services.project_graph.extractor_registry as extractor_registry
import services.project_graph.llm_extractor as llm_extractor
from services.project_graph import ProjectSemanticExtractionResult, ProjectSourceSegment


def _payload() -> llm_extractor.ExtractionPayload:
    return llm_extractor.ExtractionPayload(objects=[], relations=[])


def _response(*, parsed=None, content=None):
    return types.SimpleNamespace(
        choices=[
            types.SimpleNamespace(
                message=types.SimpleNamespace(parsed=parsed, content=content)
            )
        ]
    )


class _FakeOpenAIClient:
    def __init__(self, *, parsed_payload=None, content=None) -> None:
        self.parse = AsyncMock(return_value=_response(parsed=parsed_payload))
        self.create = AsyncMock(return_value=_response(content=content))
        self.beta = types.SimpleNamespace(
            chat=types.SimpleNamespace(
                completions=types.SimpleNamespace(parse=self.parse)
            )
        )
        self.chat = types.SimpleNamespace(
            completions=types.SimpleNamespace(create=self.create)
        )
        self.close = AsyncMock()


def _install_client(monkeypatch, client: _FakeOpenAIClient) -> None:
    monkeypatch.setattr(
        llm_extractor,
        "build_llm_provider_http_client",
        AsyncMock(return_value=("https://provider.example/v1", object())),
    )
    monkeypatch.setattr(llm_extractor, "AsyncOpenAI", lambda **_kwargs: client)


@pytest.mark.asyncio
async def test_direct_provider_keeps_native_structured_output(monkeypatch) -> None:
    payload = _payload()
    client = _FakeOpenAIClient(parsed_payload=payload)
    _install_client(monkeypatch, client)

    result = await llm_extractor._call_llm(
        api_key="key",
        base_url="https://provider.example/v1",
        model="direct-model",
        segments_json='{"segments": []}',
        routed_via_orchestrator=False,
    )

    assert result == payload
    client.parse.assert_awaited_once()
    client.create.assert_not_awaited()
    request = client.parse.await_args.kwargs
    assert request["response_format"] is llm_extractor.ExtractionPayload
    assert "extra_body" not in request
    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_orchestrator_uses_auto_without_single_worker_passthrough(monkeypatch) -> None:
    payload = _payload()
    client = _FakeOpenAIClient(content=payload.model_dump_json())
    _install_client(monkeypatch, client)

    result = await llm_extractor._call_llm(
        api_key="key",
        base_url="https://orchestrator.example/v1",
        model="contextual-orchestrator",
        segments_json='{"segments": []}',
        routed_via_orchestrator=True,
    )

    assert result == payload
    client.create.assert_awaited_once()
    client.parse.assert_not_awaited()
    request = client.create.await_args.kwargs
    assert request["extra_body"] == {
        "orchestration_mode": "auto",
        "include_orchestration_trace": False,
    }
    assert "response_format" not in request
    client.close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [None, "", "not-json", "[]"])
async def test_orchestrator_output_fails_closed_when_schema_is_invalid(
    monkeypatch, content
) -> None:
    client = _FakeOpenAIClient(content=content)
    _install_client(monkeypatch, client)

    with pytest.raises(RuntimeError, match="unparsable payload"):
        await llm_extractor._call_llm(
            api_key="key",
            base_url="https://orchestrator.example/v1",
            model="contextual-orchestrator",
            segments_json='{"segments": []}',
            routed_via_orchestrator=True,
        )

    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_registry_marks_only_orchestrator_transport_as_adaptive(
    monkeypatch,
) -> None:
    observed: dict[str, object] = {}

    async def fake_extract(_segments, **kwargs):
        observed.update(kwargs)
        return ProjectSemanticExtractionResult(
            objects=(),
            edges=(),
            extractor_name="test_extractor",
            extractor_version="1.0.0",
        )

    monkeypatch.setattr(
        extractor_registry, "extract_project_semantics_llm", fake_extract
    )
    extractor = extractor_registry.LlmGroundedExtractor(
        routed_via_orchestrator=True
    )
    context = extractor_registry.KgExtractorContext(
        api_key="key",
        model="contextual-orchestrator",
        orchestrator_base_url="https://orchestrator.example/v1",
    )
    segment = ProjectSourceSegment(
        content_segment_uid="seg1",
        source_kind="email_body",
        source_record_uid="email:1",
        safe_text_content="A grounded requirement.",
        heading_path=None,
        segment_path="body/0",
        ordinal_index=0,
    )

    await extractor.extract([segment], context=context)

    assert observed["routed_via_orchestrator"] is True
'''

ADR_CONTENT = '''# ADR-0100: Adaptive contextual-orchestrator mode is the project-graph default

- Status: Accepted
- Date: 2026-08-16

## Context

Naruon's project-graph extractor can call either a direct OpenAI-compatible provider or contextual-orchestrator. Both paths previously used the provider-native structured-output parser. Contextual-orchestrator intentionally proxies requests carrying provider-native `response_format` to one worker because the complete provider envelope cannot be merged losslessly, so the nominal orchestrator path was effectively fixed single-model routing.

## Decision

The direct-provider path retains native structured output. The contextual-orchestrator path instead:

- calls the ordinary chat-completions transport;
- includes `orchestration_mode: "auto"` and disables orchestration-trace disclosure;
- omits provider-native `response_format`;
- validates the returned assistant text locally with the exact Pydantic `ExtractionPayload` contract;
- fails closed to the existing deterministic extractor chain on missing or malformed output.

Contextual-orchestrator owns model/provider selection, test-time compute, workflow depth, verification, fallback, and known-price optimization. Quality sufficiency is the first constraint; cost is minimized among quality-sufficient paths. Missing or untrusted price metadata is classified as unpriced, not free.

Naruon continues to own segment-citation grounding, controlled object and relation vocabularies, confidence bounds, SSRF-allowlisted transport, and deterministic fallback. Explicit fixed modes are reserved for controlled ablation or a documented incident override and are not product defaults.

## Consequences

A simple extraction may still use one worker when adaptive policy finds that sufficient. Difficult extraction can receive deeper orchestration without changing Naruon's public API. Direct providers remain compatible with the native structured-output contract.

## References

Omidvar, H., & Akhlaghi, V. (2026). *A communication-theoretic framework for LLM agents: Cost-aware adaptive reliability* [Preprint]. arXiv. https://doi.org/10.48550/arXiv.2605.09121

Tang, Y., Cetin, E., Xu, J., Sun, Q., Nielsen, S., Richard, V., Goda, H., Tymchenko, I., Nguyen, N., Lee, H., Ashiga, M., Kotyan, S., Kuroki, S., & Clanuwat, T. (2026). *Sakana Fugu technical report* [Technical report]. arXiv. https://doi.org/10.48550/arXiv.2606.21228
'''


def replace_once(path: Path, old: str, new: str) -> None:
    """Replace exactly one source fragment or fail closed."""
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}: {old!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def write_test() -> None:
    """Write only the failing transport contract."""
    if TEST_PATH.exists():
        raise SystemExit(f"refusing to overwrite {TEST_PATH}")
    TEST_PATH.write_text(TEST_CONTENT, encoding="utf-8")


def implement() -> None:
    """Separate direct structured output from adaptive orchestrator transport."""
    replace_once(
        SOURCE_PATH,
        "from pydantic import BaseModel",
        "from pydantic import BaseModel, ValidationError",
    )
    replace_once(
        SOURCE_PATH,
        'LLM_EXTRACTOR_VERSION = "2026.07.13.1"',
        'LLM_EXTRACTOR_VERSION = "2026.08.16.1"',
    )
    old_call = '''async def _call_llm(
    *,
    api_key: str,
    base_url: str | None,
    model: str,
    segments_json: str,
) -> ExtractionPayload:
    """Isolated network seam so tests can fake the provider response."""
    validated_base_url, http_client = await build_llm_provider_http_client(base_url)
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=validated_base_url,
        http_client=http_client,
    )
    try:
        response = await client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": _system_instruction()},
                {"role": "user", "content": f"SEGMENTS_JSON: {segments_json}"},
            ],
            response_format=ExtractionPayload,
        )
    finally:
        await client.close()

    parsed = response.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("LLM extraction returned an unparsable payload")
    return parsed
'''
    new_call = '''async def _call_llm(
    *,
    api_key: str,
    base_url: str | None,
    model: str,
    segments_json: str,
    routed_via_orchestrator: bool = False,
) -> ExtractionPayload:
    """Call a direct provider or adaptive orchestrator and validate one payload.

    Direct providers retain their native structured-output contract. The
    contextual-orchestrator path deliberately omits ``response_format`` because
    that feature is proxied to one worker; ordinary chat output is instead
    parsed locally against the exact Pydantic schema and fails closed.
    """
    validated_base_url, http_client = await build_llm_provider_http_client(base_url)
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=validated_base_url,
        http_client=http_client,
    )
    messages = [
        {"role": "system", "content": _system_instruction()},
        {"role": "user", "content": f"SEGMENTS_JSON: {segments_json}"},
    ]
    try:
        if routed_via_orchestrator:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                extra_body={
                    "orchestration_mode": "auto",
                    "include_orchestration_trace": False,
                },
            )
            content = response.choices[0].message.content
            if not isinstance(content, str) or not content.strip():
                raise RuntimeError("LLM extraction returned an unparsable payload")
            try:
                return ExtractionPayload.model_validate_json(content)
            except ValidationError as exc:
                raise RuntimeError(
                    "LLM extraction returned an unparsable payload"
                ) from exc

        response = await client.beta.chat.completions.parse(
            model=model,
            messages=messages,
            response_format=ExtractionPayload,
        )
        parsed = response.choices[0].message.parsed
        if parsed is None:
            raise RuntimeError("LLM extraction returned an unparsable payload")
        return parsed
    finally:
        await client.close()
'''
    replace_once(SOURCE_PATH, old_call, new_call)
    replace_once(
        SOURCE_PATH,
        '''async def extract_project_semantics_llm(
    segments: Iterable[ProjectSourceSegment],
    *,
    api_key: str,
    base_url: str | None = None,
    model: str,
) -> ProjectSemanticExtractionResult:''',
        '''async def extract_project_semantics_llm(
    segments: Iterable[ProjectSourceSegment],
    *,
    api_key: str,
    base_url: str | None = None,
    model: str,
    routed_via_orchestrator: bool = False,
) -> ProjectSemanticExtractionResult:''',
    )
    replace_once(
        SOURCE_PATH,
        '''        model=model,
        segments_json=_segments_json(segment_list),
    )''',
        '''        model=model,
        segments_json=_segments_json(segment_list),
        routed_via_orchestrator=routed_via_orchestrator,
    )''',
    )
    replace_once(
        REGISTRY_PATH,
        '''            api_key=context.api_key,
            base_url=base_url,
            model=context.model,
        )''',
        '''            api_key=context.api_key,
            base_url=base_url,
            model=context.model,
            routed_via_orchestrator=self.routed_via_orchestrator,
        )''',
    )
    replace_once(
        CHANGELOG_PATH,
        "## [Unreleased]\n",
        "## [Unreleased]\n- contextual-orchestrator 기반 프로젝트 그래프 추출은 이제 provider-native structured-output 단일-worker passthrough를 사용하지 않고 `auto` orchestration을 명시합니다. 반환 JSON은 동일한 Pydantic 계약으로 로컬 검증되며 오류 시 기존 결정론적 추출기 체인으로 fail closed 합니다. 직접 OpenAI 호환 provider는 기존 native structured-output 경로를 유지합니다.\n",
    )
    ADR_PATH.parent.mkdir(parents=True, exist_ok=True)
    if ADR_PATH.exists():
        raise SystemExit(f"refusing to overwrite {ADR_PATH}")
    ADR_PATH.write_text(ADR_CONTENT, encoding="utf-8")


def main() -> None:
    """Run one bounded bootstrap phase."""
    if len(sys.argv) != 2 or sys.argv[1] not in {"test", "implement"}:
        raise SystemExit("usage: bootstrap_quality_cost_auto_default.py test|implement")
    if sys.argv[1] == "test":
        write_test()
    else:
        implement()


if __name__ == "__main__":
    main()
