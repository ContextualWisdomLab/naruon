# Structural Topic Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove keyword-triggered pseudo-topic classification from Naruon's
product surface and document the fail-closed TEPP STM boundary.

**Architecture:** Naruon's generic tool registry will retain honest lexical
utilities but will no longer expose fixed dictionaries as topic inference or
agenda generation. Corpus-level STM remains an external Rust-first TEPP
measurement boundary whose future posterior contract is documented here rather
than simulated in the request handler.

**Tech Stack:** Python 3.12+, FastAPI tool registry, pytest, Ruff, Markdown.

## Preflight

- [ ] Read the repository-root `AGENTS.md` before any edit and apply every
  instruction whose scope covers the files below.

## Global Constraints

- Do not introduce keyword, embedding, or LLM fallback topic classification.
- Do not claim that a fixed business label is an STM posterior probability.
- Preserve `ANALYSIS_TEXT_MAX_CHARS` enforcement for the retained lexical tool.
- Treat every warning as a verification failure.
- Keep the change atomic and avoid unrelated tool-registry refactoring.

## Complete PR File Inventory

- Modify: `AGENTS.md`
- Modify: `CHANGELOG.md`
- Modify: `backend/api/tools.py`
- Modify: `backend/tests/test_tools_api.py`
- Create: `docs/adr/README.md`
- Create: `docs/adr/0001-topic-measurement-authority.md`
- Create: `docs/doctoring/structural-topic-model-boundary.md`
- Create: `docs/superpowers/plans/2026-08-09-structural-topic-boundary.md`
- Create:
  `docs/superpowers/specs/2026-08-09-structural-topic-boundary-design.md`

---

### Task 1: Lock out lexical pseudo-topic tools

**Files:**
- Modify: `backend/tests/test_tools_api.py`
- Modify: `backend/api/tools.py`

**Interfaces:**
- Consumes: the existing module-level `registry: ToolRegistry`.
- Produces: a registry without `email_categorizer` or
  `meeting_agenda_generator`; `keyword_extractor` remains registered and is
  explicitly described as term-frequency extraction.

- [ ] **Step 1: Write the failing registry-contract test**

```python
@pytest.mark.parametrize(
    "tool_code", ["email_categorizer", "meeting_agenda_generator"]
)
def test_registry_omits_lexical_pseudo_topic_tools(tool_code):
    assert registry.get(tool_code) is None


def test_keyword_extractor_is_disclosed_as_lexical_term_frequency():
    tool = registry.get("keyword_extractor")
    assert tool is not None
    assert tool.description == (
        "텍스트 본문에서 빈도와 최초 출현 순으로 반복 용어를 추출합니다."
    )
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:
`PYTHONWARNINGS=error DISABLE_BACKGROUND_WORKERS=1 uv run --project backend --frozen python -m pytest backend/tests/test_tools_api.py::test_registry_omits_lexical_pseudo_topic_tools backend/tests/test_tools_api.py::test_keyword_extractor_is_disclosed_as_lexical_term_frequency -q`

Expected: the first test fails because both pseudo-topic tools are registered;
the second fails because the current description overclaims importance.

- [ ] **Step 3: Remove the pseudo-model implementation**

Delete `_CATEGORY_TERMS`, `_AGENDA_TOPICS`, `_contains_analysis_term`, both
handlers, both `registry.register(...)` blocks, and their behavior-locking tests.
Change the retained handler docstring to
`"""Extract deterministic lexical terms by frequency and first occurrence."""`
and its tool description to
`"텍스트 본문에서 빈도와 최초 출현 순으로 반복 용어를 추출합니다."`.

- [ ] **Step 4: Run the focused test file and verify GREEN**

Run:
`PYTHONWARNINGS=error DISABLE_BACKGROUND_WORKERS=1 uv run --project backend --frozen python -m pytest backend/tests/test_tools_api.py -q`

Expected: all tests pass with no warning-class output.

### Task 2: Record the scientific and governance boundary

**Files:**
- Modify: `AGENTS.md`
- Modify: `CHANGELOG.md`
- Create: `docs/adr/README.md`
- Create: `docs/adr/0001-topic-measurement-authority.md`
- Create: `docs/doctoring/structural-topic-model-boundary.md`
- Create:
  `docs/superpowers/specs/2026-08-09-structural-topic-boundary-design.md`
- Create: `docs/superpowers/plans/2026-08-09-structural-topic-boundary.md`

**Interfaces:**
- Consumes: the decision in
  `docs/superpowers/specs/2026-08-09-structural-topic-boundary-design.md`.
- Produces: a durable anti-pattern rule, user-visible change record, and APA 7
  research note.

- [ ] **Step 1: Add the anti-pattern rule**

State that topic inference must not be implemented with hard-coded term lists,
term frequency, embeddings, or LLM labels presented as STM; unavailability of a
fitted TEPP model must fail closed.

- [ ] **Step 2: Add the changelog entry**

Under the current unreleased section, record removal of the two misleading tools
and preservation of the honest lexical utility.

- [ ] **Step 3: Add the doctoring note**

Document the defect history, distinction between STM and classification, future
TEPP contract, and APA 7 references with DOI links. Check each source's
redistribution license first. If the license permits repository distribution,
store the PDF and record that license; otherwise attach no PDF and provide the
citation, stable link, and a concise summary of why the source supports this
boundary.

### Task 3: Verify and publish

**Files:**
- Verify all files changed by Tasks 1 and 2.

**Interfaces:**
- Consumes: the completed atomic diff.
- Produces: exact local evidence and a GitHub pull request based on the current
  `develop` head.

- [ ] **Step 1: Run Ruff**

Run:
`uv run --project backend --frozen python -m ruff check backend/api/tools.py backend/tests/test_tools_api.py`

Expected: exit 0 and no diagnostics.

- [ ] **Step 2: Run the complete backend suite**

Run:
`PYTHONWARNINGS=error DISABLE_BACKGROUND_WORKERS=1 uv run --project backend --frozen python -m pytest backend -q`

Expected: exit 0 with no `Timeout`, `Fatal`, `Warn`, or `Denied` output.

- [ ] **Step 3: Inspect the exact diff**

Run: `git diff --check origin/develop..HEAD` and
`git diff --stat origin/develop..HEAD`, then enforce the exact allowlist:

```bash
uv run --project backend --frozen python - <<'PY'
import subprocess

expected = {
    "AGENTS.md",
    "CHANGELOG.md",
    "backend/api/tools.py",
    "backend/tests/test_tools_api.py",
    "docs/adr/README.md",
    "docs/adr/0001-topic-measurement-authority.md",
    "docs/doctoring/structural-topic-model-boundary.md",
    "docs/superpowers/plans/2026-08-09-structural-topic-boundary.md",
    "docs/superpowers/specs/2026-08-09-structural-topic-boundary-design.md",
}
actual = set(
    subprocess.check_output(
        ["git", "diff", "--name-only", "origin/develop..HEAD"], text=True
    ).splitlines()
)
assert actual == expected, {
    "unexpected": sorted(actual - expected),
    "missing": sorted(expected - actual),
}
PY
```

Expected: no whitespace errors and an exact allowlist match, with no unrelated
files.

- [ ] **Step 4: Commit and open a pull request**

Commit message: `fix(tools): remove lexical pseudo-topic models`.
Push `fix/remove-lexical-topic-heuristics` and open a PR against `develop` with
the exact test commands and the TEPP follow-up boundary in the body. Record
each predecessor-head validation as historical with its actual passed, failed,
or cancelled outcome; label only successful predecessor validation as passed.
Mark current exact-head CI and security checks as pending until GitHub produces
that evidence, and do not describe predecessor results as current.

- [ ] **Step 5: Require current-head CI evidence**

Record the exact PR head SHA after every push or other head-changing commit.
Local validation or CI attached to a predecessor SHA is historical context only
and must never be promoted as current evidence. Before merge, every required
GitHub check must report success for the exact current PR head; rerun or request
checks whenever that head changes. Replace each pending PR-body item with a link
or stable run reference that identifies both the successful required check and
that exact head SHA.
