# Strix scanner dependency floor repair

This is a scratch-only proposal for canonical Naruon PR #1828 at
`74f9d6dd3b34d1179ca5f2aa3c5c294d22c7d2b2`; it is not adopted or merged.
PR #1843 at `e40f8c65e4404d8446f8c4fb3ae84e0d6b3d68e4` is input only.
Its isolated LiteLLM 1.93.2 delta does not repair the other three lock findings.

## Narrow dependency change

Keep Strix 1.0.4 and all other 98 resolved versions unchanged. Pin the four
patched transitive packages explicitly in `requirements-strix-ci.txt`, then
update only their generated hash-lock records:

| Package | Before | Proposed |
| --- | --- | --- |
| aiohttp | 3.14.1 | 3.14.3 |
| LiteLLM | 1.89.2 | 1.89.7 |
| PyJWT | 2.13.0 | 2.15.0 |
| urllib3 | 2.7.0 | 2.8.0 |

GHSA-3cv6-jpf6-8222 lists 1.89.7 as the patched 1.89-series release, and
1.93.2 as a separate series patch. Choose the smaller 1.89.7 change; do not
assume every numerically newer minor-series version is patched. Source:
<https://github.com/advisories/GHSA-3cv6-jpf6-8222>.
The new scanner contract also rejects the advisory's known later affected
maintenance-series intervals. Future advisories still require a live audit.

## Reproduce without unrelated upgrades

Use Python 3.13 for this scanner graph. The original lock generation header
already targets 3.13/Linux x86_64. Installed Strix metadata supports >=3.12,
but LiteLLM 1.89.7 metadata requires `>=3.10,<3.14`; application Python 3.14
is not permission to install this scanner graph on 3.14.

Generate a temporary constraints file from every original exact lock pin,
changing only the four values above. Preserve it outside the source proposal.
From the repository root:

```sh
uv pip compile --generate-hashes --python-version 3.13 \
  --python-platform x86_64-unknown-linux-gnu \
  --constraint /absolute/path/to/constrained-pins.txt \
  --output-file /absolute/path/to/generated-full-lock.txt requirements-strix-ci.txt
uv venv --python 3.13 /absolute/path/to/isolated-scanner-venv
uv pip install --python /absolute/path/to/isolated-scanner-venv/bin/python \
  --require-hashes -r requirements-strix-ci-hashes.txt
uv pip check --python /absolute/path/to/isolated-scanner-venv/bin/python
python -m pytest backend/tests/test_scanner_dependency_security_contract.py \
  backend/tests/test_container_dependency_pin_contract.py \
  backend/tests/test_release_governance.py -q
```

The proposal takes the four complete artifact/hash records from the resolver
output and retains the other original records byte-for-byte. Assert complete
102-package map equality with the resolver before doing so. Do not preserve
scratch-only constraint annotations in the committed lock. The existing lock
header remains the standard unconstrained regeneration command; the constrained
repair receipt is retained separately, not silently represented as a full
unconstrained byte-identical regeneration.

## Measured evidence and limits (2026-10-03)

The four new cases failed on the original lock, then the new cases plus existing
container/release contracts passed: 41 tests, zero skips. A fresh Python 3.13.15
macOS arm64 environment installed all 102 candidate records with required
hashes; `uv pip check` passed. Installed package inventory equals the proposed
lock exactly. Linux x86_64 resolution is verified, not a Linux native install.

Real OSV `/v1/querybatch` calls queried every one of the 102 baseline and
candidate versions without ignores or severity filtering. Baseline: four
affected packages, 40 advisory records (aliases are not distinct CVEs), exit 1.
Candidate: zero records, exit 0. This is a complete scanner-lock audit, not a
whole-repository/frontend/image audit or a hosted gate result.

Offline installed-supplier probes imported Strix/LiteLLM, registered Strix cost
callbacks, constructed its real SDK LiteLLM adapter for Vertex and DeepSeek
model names, and ran the installed CLI's `--version` and `--help`. Socket/DNS,
subprocess and private-file access were blocked by an audit hook. No provider
requests, inference, targets, scans, Docker processes or telemetry were run.
Adapter construction is not proof of provider availability or GitHub Models
routing; that control remains owned by the central workflow.

The initial offline probes failed because python-dotenv attempted parent `.env`
discovery; the hook stopped the open before content was read. Retain those
failures. Repeat with the supplier-supported `PYTHON_DOTENV_DISABLED=true` and
`LITELLM_LOCAL_MODEL_COST_MAP=true` bootstrap controls, not warning filters.
Successful retries emitted no warnings and attempted no prohibited I/O.

All exact commands, exits, raw logs, request/response bytes, maps and patch
hashes are in the sibling scratch evidence packet. Independent source review,
canonical-owner adoption and exact-head warning-clean hosted acceptance remain
required. No credentials, controls, workflows or existing parent tests change.
