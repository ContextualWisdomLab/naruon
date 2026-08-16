# PyPI release-hash provenance for Python locks

## Status and ownership

**Status:** Implemented on active PR only. This document does not describe protected `develop` until the corresponding code is merged.

Naruon owns this repository-local supply-chain gate because it validates the Python lock files Naruon executes in CI and release preparation. PyPI remains the external release-metadata authority for this bounded public-index check. The gate does not copy dependency-policy authority from another CWL repository.

## Buyer and operator decision

A syntactically valid `--hash=sha256:` value is not sufficient evidence that a lock actually names a file published for the declared package release. Before dependency installation, Naruon therefore compares each exact project/version lock entry with trusted PyPI release metadata and requires at least one SHA-256 intersection with an eligible artifact.

A passing receipt means the operator may continue to later dependency-install and platform-compatibility gates. A failing receipt means the operator should regenerate or investigate the lock; it must not be treated as a transient application-test failure or bypassed.

## Implemented boundary

For every discovered active `requirements*.txt` hash lock, the validator:

1. reads only repository-contained UTF-8 files;
2. requires exact `==` pins and attached SHA-256 values;
3. normalizes project names before metadata resolution;
4. queries the exact PyPI release route `GET /pypi/<project>/<version>/json` over credential-free HTTPS;
5. binds returned `info.name` and `info.version` to the requested release;
6. considers only non-yanked `bdist_wheel` and `sdist` file objects with a syntactically valid SHA-256 digest;
7. requires at least one intersection between those published digests and the hashes recorded in the lock;
8. emits path-relative, deterministic reason codes and match counts without artifact URLs, provider exception strings, credentials, or absolute runner paths;
9. caches release metadata per `(project, version)` during one repository scan so repeated pins do not multiply external requests.

Application CI runs this network-derived evidence after the deterministic offline lock-declaration gate and before dependency installation.

## Failure semantics

The gate is fail-closed. Important stable reasons include:

- `lock-path-outside-repository`: a lock resolves outside the repository root;
- `lock-read-failed`: the lock cannot be read as repository UTF-8 text;
- `lock-requirement-not-exact`: a requirement is not an exact `==` pin;
- `lock-requirement-has-no-sha256`: an exact pin has no attached SHA-256;
- `registry-metadata-fetch-failed`: exact PyPI release metadata could not be resolved;
- `registry-project-mismatch` / `registry-version-mismatch`: returned metadata does not identify the requested release;
- `registry-release-has-no-allowed-artifacts`: the release has no eligible non-yanked wheel or source distribution SHA-256;
- `registry-hash-mismatch`: eligible release artifacts exist but none of their SHA-256 values appears in the lock.

Network/provider exception text is deliberately not copied into the machine receipt. The workflow log may contain transport diagnostics from the trusted runtime, but the persisted summary is bounded to non-secret decision evidence.

## Why PyPI release JSON is used in this slice

The Python Packaging User Guide defines the Simple Repository API as the standards-track index interface and specifies JSON file records with hash dictionaries; PyPI recommends JSON for new index integrations. PyPI also documents a release-specific JSON route whose `urls` entries include file type, yanked state, and SHA-256 digests for one exact release. This bounded slice uses that release-specific PyPI route because it directly binds the requested exact version to its current file list without downloading or executing distributions.

This is intentionally a **PyPI-specific adapter**, not a claim of generic PEP 691/private-index support. A future provider-neutral index adapter should consume the Simple Repository JSON API with explicit repository authority, TLS/origin policy, version selection, and index-isolation tests rather than silently redirecting this gate to an arbitrary host.

## Relationship to pip hash checking

pip's secure-install guidance describes `--require-hashes` as an all-or-nothing mode: requirements and dependencies need hashes and should be pinned, with multiple hashes often necessary when multiple wheels or source distributions are acceptable. It also distinguishes locally recorded hashes from remotely supplied index hashes. Naruon's registry receipt complements rather than replaces that control: it verifies that at least one local lock hash corresponds to an eligible file PyPI currently publishes for the exact release; later CI still performs `pip install --require-hashes`.

## Explicit non-claims and follow-on work

A passing receipt does **not** yet prove:

- that the matched wheel is compatible with Python 3.14, the runner ABI, operating system, or architecture;
- that a source distribution is acceptable for the deployment policy;
- complete transitive dependency closure;
- clean installation on every supported Python/platform target;
- parity with a private or mirrored package index;
- that an artifact is covered by a trusted publisher attestation or PEP 740 provenance statement;
- reproducible wheel build output from an sdist.

Issue #1229 remains open until those applicable boundaries, especially target-aware artifact matching and clean `pip install --require-hashes` rehearsal, have executable evidence.

## Security and privacy analysis

The built-in network path accepts only credential-free `https://pypi.org` as its origin. Project and version values become percent-encoded path segments; the receipt never copies returned file URLs. Metadata response size and content type are bounded before JSON parsing. No provider credential is needed or permitted for this public-index slice.

The main residual risk is authority scope: proving a hash is published by PyPI is not the same as proving publisher identity, artifact intent, target compatibility, or absence of compromise. Those remain separate gates rather than being collapsed into one green status.

## Verification

The active PR uses RED-first tests covering matching and stale hashes, yanked and unsupported artifact types, release-identity mismatch, provider failure redaction, repeated-release fetch deduplication, trusted-origin validation, deterministic path-relative receipts, and CI ordering before installation. Exact current-head GitHub checks and independent review remain authoritative; predecessor-head results do not transfer.

## References

Python Packaging Authority. (n.d.). *Simple repository API*. Python Packaging User Guide. Retrieved August 16, 2026, from https://packaging.python.org/en/latest/specifications/simple-repository-api/

Python Packaging Authority. (n.d.). *Secure installs*. pip documentation. Retrieved August 16, 2026, from https://pip.pypa.io/en/stable/topics/secure-installs/

Python Package Index. (n.d.). *Index API*. PyPI Docs. Retrieved August 16, 2026, from https://docs.pypi.org/api/index-api/

Python Package Index. (n.d.). *JSON API*. PyPI Docs. Retrieved August 16, 2026, from https://docs.pypi.org/api/json/
