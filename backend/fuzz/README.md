# Fuzzing the untrusted-input parsers

This directory fuzzes the surfaces that ingest attacker-controlled data — raw
provider email, HTML/markdown bodies, and email attachments — and asserts they
degrade gracefully (no crash, declared-exception-only, structural invariants
hold) on arbitrary input.

## Targets

| Target module | Entry point | Harness |
| --- | --- | --- |
| `services/email_parser.py` | `parse_eml_bytes` (raw MIME bytes) | `test_email_parser_fuzz.py`, `fuzz_email_parser.py` |
| `services/text_safety.py` | `strip_html_markup` (HTML sanitiser) | `test_text_safety_fuzz.py`, `fuzz_text_safety.py` |
| `services/content_graph/parser.py` | `parse_content` (HTML/markdown/plain → graph) | `test_content_graph_fuzz.py`, `fuzz_content_graph.py` |
| `services/attachment_parser.py` | `parse_email_attachment` | `test_attachment_parser_fuzz.py`, `fuzz_attachment_parser.py` |

These were selected with CodeGraph (`codegraph explore "parse email …"`,
`"content graph parser …"`, `"strip html markup …"`) as the highest-value
untrusted-input surfaces: each parses attacker-supplied bytes, and CodeGraph
confirmed `parse_email_attachment` fans out to 8 callers in `email_parser.py`.

The invariants each harness checks live once in [`_invariants.py`](./_invariants.py)
and are shared by both the Hypothesis and the Atheris drivers.

## Two engines, both permissive-licensed

- **Hypothesis** (MPL-2.0) — property-based, pure Python, always runnable under
  pytest. This is the CI gate.
- **Atheris** (Apache-2.0) — coverage-guided (libFuzzer). Optional; Atheris has
  no wheels for every Python version, so CI installs it best-effort.

## Running locally

```bash
cd backend

# Fast property run (default "dev" profile, ~50 examples/target)
python -m pytest fuzz -q

# Larger budget (CI profile, 1000 examples/target by default)
HYPOTHESIS_PROFILE=ci python -m pytest fuzz -q

# Deep local campaign
HYPOTHESIS_PROFILE=ci HYPOTHESIS_MAX_EXAMPLES=50000 python -m pytest fuzz -q

# Coverage-guided (needs `pip install atheris`, Python <= 3.12)
python fuzz/fuzz_email_parser.py -max_total_time=60 fuzz/corpus/email
```

## CI

[`.github/workflows/fuzz.yml`](../../.github/workflows/fuzz.yml) runs the four
Hypothesis targets in parallel on every PR with a small, wall-clock-capped
budget (150s hard cap per target — actual runtime is a few seconds), plus a
larger nightly schedule. The primary `Application CI` test job does not install
Hypothesis; the property tests `importorskip` it and are skipped there, so the
existing suite is unaffected.

## Findings

The email-parser target found (and this change fixes) two real crashes in the
ingest path, where `_message_to_email_data` ran outside `parse_eml_bytes`'
`try/except`:

1. A non-ASCII addr-spec (IDN domain, or an RFC 2047 encoded-word `From` that
   `getaddresses` parses as the address) made `email.utils.formataddr` raise
   `UnicodeEncodeError`. Fixed with `_safe_formataddr`.
2. A message declaring `multipart/*` with no parsable parts (reported as
   single-part) made `Message.get_content()` raise `KeyError`. Fixed by guarding
   the single-part body path like the attachment path already was.

Both are additionally normalised to the declared `EmailParseError`.
