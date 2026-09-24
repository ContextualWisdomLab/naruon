# Starlette TestClient `httpx2` dependency

## Observed failure

Protected `develop@042b0c70531b229af3acbd0421a2f23098d848b3` pins Starlette
1.3.1 but did not install Starlette's preferred `httpx2` TestClient transport.
Importing `starlette.testclient` therefore fell back to deprecated `httpx`, and
warnings-as-errors runs stopped during collection. Removing the warning filter
without installing the preferred transport would expose the defect without
repairing it.

## Decision and dependency boundary

Pin `httpx2==2.13.0` and resolved `httpcore2==2.13.0` in the repository's
core development/test graph. The Noema-agent lock participates in the same
`pip --require-hashes` transaction as the core lock, so it carries the exact
same `httpx2`/`httpcore2` records and hash sets instead of retaining the old
2.5.0 graph. `genai-prices==0.0.71` requires `httpx2>=2.0`, so this coherent
pin stays within its declared consumer contract.

The generated `uv.lock` also records the 2.13.0 platform split: `httpcore2`
on non-Emscripten platforms and `httpx2-jsfetch==1.0` on Emscripten. Naruon's
application HTTP clients remain on their existing `httpx` path; this change is
the Starlette TestClient transport boundary, not an application-client rewrite.

The accepted five-file candidate was generated read-only with Python 3.14 and
`uv==0.10.0`, then checked as one core+agent hash-locked dry-run. Artifact
`10748790356` from Application CI `35844541085` has archive digest
`sha256:5355320323967e3cd58bdd8f05d1914c63d68790f28bf28b47bfba7fe019942b`.
Its independently verified file digests are:

- `requirements.txt`: `87f603d06eb05fa234163003a2feda98f024b80751cc9eb919aedb261136482f`;
- `pyproject.toml`: `faab5edd236153c28a321e431dc1a6d5f99bcaa64f26f21c60222a1db2057365`;
- `requirements-hashes.txt`: `551f6aa4a6a8f1efb7f6259dc63777c40c09b2f520dea217575b94b12178f7d5`;
- `requirements-agent.txt`: `761ceb9f7042ffa9538c5a596ad113a3ee59f27381c4a44d34df82338e5b913a`;
- `uv.lock`: `fa28138f637a2c2baddd528893cfb04be2d9064afcadd538fb7fa5000be7f82b`.

These digests establish the adopted bytes; they do not transfer merge or
release authority. Temporary adoption machinery is removed after the product
commit is verified so the normal exact-head gates evaluate only product source.

## Verification and rollback

Run from the repository root:

```bash
cd backend && uv lock --check
python -m pip install --disable-pip-version-check --require-hashes \
  -r backend/requirements-hashes.txt -r backend/requirements-agent.txt
cd backend && python -m pytest -q -W error tests/test_container_dependency_pin_contract.py
cd backend && python -m ruff check tests/test_container_dependency_pin_contract.py
```

The structural regression verifies the direct 2.13.0 pin, the core hash-lock
records, exact core/agent hash equality for `httpx2` and `httpcore2`, and the
runtime module selected by `starlette.testclient`. Full acceptance still
requires the normal helper-free current-head Application CI, Security, CodeQL,
required workflows and qualifying independent review.

Rollback removes the direct pin, both coherent lock records, runtime assertion,
and obsolete-warning-filter removal together. Do not restore only the warning
suppression or leave the core and optional-agent locks on different graphs.

## References

Kludex. (2026). *Starlette release notes*. GitHub.
https://github.com/Kludex/starlette/blob/main/docs/release-notes.md

Python Packaging Authority. (2026). *httpx2 2.13.0 file details and provenance*.
PyPI. https://pypi.org/project/httpx2/2.13.0/

Pydantic. (2026). *HTTPX2 v2.13.0* [Source code]. GitHub.
https://github.com/pydantic/httpx2/tree/v2.13.0
