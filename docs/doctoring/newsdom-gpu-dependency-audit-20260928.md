# NewsDOM GPU dependency audit

Supplier source: `927ff2dec160a00ed11ec045727a422ff7ba4cbd` (canonical newsdom-api #822).

The API runtime lock audit does not cover the second NVIDIA Dockerfile install:
`uv pip install "mineru[pipeline]==3.4.4"`. Resolve and audit that combined set before accepting this runtime.

| Candidate | Packages | Result |
|---|---:|---|
| Existing MinerU 3.4.4 pipeline + exact API lock | 108 | 8 advisory records on Transformers 4.57.6, 5 distinct IDs |
| MinerU 4.0.7 torch + exact API lock | 142 | No known vulnerabilities in this resolved Python dependency set |

## Existing runtime findings

| Advisory | Reported fixed versions |
|---|---|
| PYSEC-2025-217 | None reported |
| PYSEC-2026-2288 | 5.0.0, 5.0.0rc3 |
| PYSEC-2026-2289 | 5.3.0 |
| PYSEC-2026-2290 | 5.5.0 |
| PYSEC-2026-3929 | 5.10.0 |

MinerU 3.4.4 and 3.4.5 both require Transformers `<5` for pipeline; several reported fixes are in 5.x. An unconstrained patch-version reinstall cannot satisfy those boundaries. No advisory suppression was used.

## Candidate resolution and scope

Target: Python 3.10, Linux x86_64 glibc 2.35 (Ubuntu 22.04). The generic Linux resolver target defaults to an older ABI and initially rejected the available llama.cpp wheel; explicitly matching the image ABI removed that false incompatibility.

Use `uv export --frozen --no-dev --no-emit-project --format requirements-txt` from the exact supplier source, include that export plus the exact MinerU extra/version in a relative requirements input, and compile with `--python-version 3.10 --python-platform x86_64-manylinux_2_35 --generate-hashes`. Audit with `pip-audit --disable-pip`.

The 4.x resolution permits source metadata only for jieba 0.42.1 (`--only-binary :all: --no-binary jieba`). Its official sdist SHA-256 `055ca12f62674fafed09427f176506079bc135638a14e23e25be909131928db2` was verified and its static distutils setup inspected first. Resolution ran with a sanitized environment; no model weights or GPU runtime packages were installed.

## Migration requirement

MinerU 4.x changes entrypoints, quality tiers, paging and result serialization. The existing 3.x runner command and artifact reader cannot be retained while swapping the package version. Use its stateless interface with all pages explicitly selected; preserve OCR mode, supported language behavior, canonical page/block geometry, and source text for exact citations. Reuse native serialization where possible.

Primary migration contract: [MinerU 4.0 release](https://github.com/opendatalab/MinerU/releases/tag/mineru-4.0.0-released). The CLI defaults to ten pages on the document-library path; that default does not satisfy full attachment parsing.

The 4.x candidate is not yet implemented in NewsDOM. These audits exclude base OS/image vulnerabilities, actual GPU/driver execution, model quality, and live OCR. Existing 3.4.4 runtime fails the dependency acceptance described above. No deployment or protected acceptance is claimed.

## Local evidence digests

- Legacy hashed resolution: `65ad54a98596eebcf98e832c79170901181109db64e1daf0f7f52e93c85c79e1` (local scratch receipt; reproduce before acceptance).
- Legacy audit: `beb837c0daad728c7b9189dcb718576978395916ee57e21f352c676dfb222e64` (local scratch receipt; reproduce before acceptance).
- 4.x hashed resolution: `1b5cb0b178c603cbb16c8dd5f4daccc9e7e5a377668f8959d4c53377732bf14d` (local scratch receipt; reproduce before acceptance).
- 4.x audit: `6409ebfe316fb6d95636e6c41b2d01caa2ad0811e68e7b2a34e6edca64a5e1ce` (local scratch receipt; reproduce before acceptance).
