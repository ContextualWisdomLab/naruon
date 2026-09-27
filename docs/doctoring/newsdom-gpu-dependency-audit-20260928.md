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

### Source-verified compatibility gaps in 4.0.7

The official PyPI wheel was checked against its published SHA-256 before reading these modules:

- `mineru/parser/mineru_parser.py`: constructor and analysis calls carry tier, OCR mode, image analysis and VLM configuration, but no OCR language selection. Source SHA-256: `ee26543dc29856996dbbfe52629fec66c7ac63f0035340aebfc639a56b8da648`.
- `mineru/model/runtime/hybrid.py`: `HybridLocalModelContext.get_ocr_model` passes literal `lang="ch"` to the atomic OCR model. Its constructor has device and small-backend parameters only. Existing NewsDOM's explicit `korean`, Arabic and other script-family requests therefore cannot be preserved by simply replacing its CLI with this public parser. Source SHA-256: `cb925a1f0c6f1c81dcff31fbb9e596806fc4fd520b8c2d0ee5618924042e6404`.
- Public `mineru.render.render_content_list` preserves `page_idx` and can replace custom block serialization. Its shared renderer converts normalized 0–1 bounding boxes to 0–1000 integer coordinates; those values must not be interpreted as physical page units without conversion. Shared-renderer source SHA-256: `6134e696525937c1441d90ac4c813a8cff47464a6c175bfaa4d391dbc8d0e2f3`.

Next implementation must thread validated language selection through the actual OCR model context, preserve coordinate units and select every page. Do not silently ignore language, substitute text-only parsing for OCR, or declare the 142-package audit sufficient runtime acceptance.

The independent existing DOM defect that omitted model-declared blank pages is repaired in [newsdom-api #958](https://github.com/ContextualWisdomLab/newsdom-api/pull/958), stacked on security-owner #822. At `65696f393224a1e08ab42fff5151cbf3639a8a4e`, 487 tests pass with warnings as errors and 100% production branch coverage. That synthetic regression proves DOM page preservation, not OCR quality or protected merge acceptance.

## Local evidence digests

- Legacy hashed resolution: `65ad54a98596eebcf98e832c79170901181109db64e1daf0f7f52e93c85c79e1` (local scratch receipt; reproduce before acceptance).
- Legacy audit: `beb837c0daad728c7b9189dcb718576978395916ee57e21f352c676dfb222e64` (local scratch receipt; reproduce before acceptance).
- 4.x hashed resolution: `1b5cb0b178c603cbb16c8dd5f4daccc9e7e5a377668f8959d4c53377732bf14d` (local scratch receipt; reproduce before acceptance).
- 4.x audit: `6409ebfe316fb6d95636e6c41b2d01caa2ad0811e68e7b2a34e6edca64a5e1ce` (local scratch receipt; reproduce before acceptance).
