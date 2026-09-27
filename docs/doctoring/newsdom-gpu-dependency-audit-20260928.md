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

Use `uv export --frozen --no-dev --no-emit-project --format requirements-txt` from the exact supplier source, include that export plus the exact MinerU extra/version in a relative requirements input, and compile with `--python-version 3.10 --python-platform x86_64-manylinux_2_35 --generate-hashes`. Audit the generated file with `pip-audit --disable-pip --require-hashes -r <compiled-file>`.

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

Source comparison with the official SHA-verified 3.4.4 wheel confirms its pipeline `_build_bbox` and VLM content-list builder also scale coordinates to 0–1000. Preserve those existing units rather than introduce a version-only rescaling. Page dimensions are a separate metadata contract. Legacy pipeline module SHA-256: `ead402d9965bf1d3723e3e36e63aa0aa6c5036565d8e6a185c430d98ff9e4878`; legacy VLM module SHA-256: `0103bbfb650d7d0de170a3b9a5ffd7829e2168ccfb443131a2db282c02b837cd`.

Next implementation must thread validated language selection through the actual OCR model context, preserve coordinate units and select every page. Do not silently ignore language, substitute text-only parsing for OCR, or declare the 142-package audit sufficient runtime acceptance.

Further source inspection narrows that language remedy: the 4.0.7 Torch OCR model resource lists only `ch` and `seal` (resource SHA-256 `52980d101f82fb549c2c33ec4b90b8266b687adf855dee2a1ac47f386192ba55`). Its recognition dictionary contains neither Hangul syllables nor Hangul jamo (SHA-256 `b5f2bfe2bdd9448429e3e82b51c789775d9b42f2403d082b00662eb77e401c5d`). Passing `korean` through alone cannot restore the old model contract. High/xhigh uses native VLM recognition; real multilingual OCR must be tested there before choosing it. This does not establish that every MinerU 4 path cannot recognize Korean.

### Isolated local execution candidate

macOS 26.5.1, Apple arm64, Python 3.13.15: the generic macOS resolver initially selected Torch 2.11 and setuptools 81, reporting three advisory records across two packages. Matching the actual supported ABI with `MACOSX_DEPLOYMENT_TARGET=14.0`, plus `torch>=2.13.0` and `setuptools>=83.0.0`, resolves 119 packages with Torch 2.14.0 and setuptools 84.0.0 and zero known vulnerabilities. Hash-enforced installation succeeded in the isolated `/tmp/newsdom-mineru4-runtime-20260928/.venv`; shared project environments were not changed.

The installed public `render_content_list` passed synthetic page-index, blank-page metadata, Korean source-text and normalized-coordinate assertions. Its strict middle schema requires metadata, a full-document flag, per-block indices and fixed-layout bounding boxes; initial incomplete synthetic records were rejected before constructing the valid fixture. This is native serialization evidence only, not OCR or Linux/NVIDIA runtime acceptance.

Local fixed-resolution SHA-256: `a49b21186897c20906b1961ed6948fbc0ff1a110b3f7ca7d15977562afac60ee`; audit SHA-256: `0b4737786890a2816f2cba79a4b52cab9a101b6a14fa4bc93e578452cb3747a9`. These are local scratch receipts and must be reproduced before acceptance.

The independent existing DOM defect that omitted model-declared blank pages is repaired in [newsdom-api #958](https://github.com/ContextualWisdomLab/newsdom-api/pull/958), stacked on security-owner #822. At `65696f393224a1e08ab42fff5151cbf3639a8a4e`, 487 tests pass with warnings as errors and 100% production branch coverage. That synthetic regression proves DOM page preservation, not OCR quality or protected merge acceptance.

## Local evidence digests

- Legacy hashed resolution: `65ad54a98596eebcf98e832c79170901181109db64e1daf0f7f52e93c85c79e1` (local scratch receipt; reproduce before acceptance).
- Legacy audit: `beb837c0daad728c7b9189dcb718576978395916ee57e21f352c676dfb222e64` (local scratch receipt; reproduce before acceptance).
- 4.x hashed resolution: `1b5cb0b178c603cbb16c8dd5f4daccc9e7e5a377668f8959d4c53377732bf14d` (local scratch receipt; reproduce before acceptance).
- 4.x audit: `6409ebfe316fb6d95636e6c41b2d01caa2ad0811e68e7b2a34e6edca64a5e1ce` (local scratch receipt; reproduce before acceptance).


## Actual macOS CPU raster OCR

The isolated 4.0.7 runtime completed native `tier="advanced"`, `ocr_mode="ocr"`,
`page_range="all"` inference through an explicit loopback llama.cpp VLM server.
The input is a synthetic three-page image PDF without embedded text, with a
blank second page. Exact assertions passed for `계약 금액: 1,200원` and
`납기: 2026년 10월 1일`, page indices `[0, 1, 2]`, and the empty middle page.
Native inference reported 1235.62 seconds; the guarded verification exited zero.
The content list contains text on pages 0 and 2; the middle JSON preserves page 1.

This revises the earlier tier assumption: advanced with the tested explicit VLM
also recognizes this Korean fixture. It does not prove all language selections,
all documents, the supplier adapter, Linux NVIDIA execution, or deployment.
Title spacing differs from the rendered source, so this is not exact transcription
of every character. Model files were downloaded at immutable revisions and
verified against publisher hashes; those hashes do not establish training quality.
The owned loopback server was stopped after terminal verification.

Scratch evidence under `/tmp/newsdom-mineru4-runtime-20260928`:

| Artifact | SHA-256 |
| --- | --- |
| synthetic-korean.pdf | b91c289f5dc106fda436361ea6ecdea71282c2643f9283285756fae964626cf0 |
| run_korean_ocr.py | df1d8c4a246b1c06a918e33202d68287730abdd5426cfa33972a03295dc75698 |
| actual-middle.json | 1826cdaadce6670ee4045bb9cfe0b0ed98cbbe7e314e1a074a794e0af19d3580 |
| actual-content-list.json | ac42a1f8f8ac714b81a80efef25c75b0238ea86270f1098ebb7784b23c9fad9a |
| model-receipts.json | 55e3f8a54fd5d1459545f8ce85a08ddd1597d761be357d1ccb32a08a64604564 |

The first unguarded helper failed because Python spawn re-executed parsing during
child-process bootstrap. Moving execution under a `__main__` guard fixed that
local helper defect; the original failure log is retained. No warning suppression,
assertion relaxation, inference deadline, or elapsed-time cancellation was added.


## Actual OCR serialization across supplier and consumer

The saved actual OCR content list was replayed through supplier PR #958's exact
`65696f393224a1e08ab42fff5151cbf3639a8a4e` DOM builder. Page dimensions came from
the original synthetic PDF's media boxes; native page indices supplied page
numbers. Pages `[1, 2, 3]` and empty page 2 are preserved. Its dependency lock
and Dockerfiles match canonical security head `927ff2dec160a00ed11ec045727a422ff7ba4cbd`.
This supplier revision passes 487 tests with warnings as errors and 100% branch
coverage.

The resulting JSON then passed Naruon's real normalization and recognition-record
builder at `5df00208d15528ccfc029f7bef385bef267c1c81`. Each exact Korean amount/date
quote appears in exactly one segment; segment text hashes, source ownership and
nonempty segment identifiers are checked. The recognized text's full-source hash
is checked independently. Empty pages remain in supplier DOM; normalization emits
content sections only on pages 1 and 3. This does not claim persisted page-number
metadata, a deployed HTTP adapter, a database write, live LLM extraction, or GPU
recognition.

The two stages use separate existing project environments and JSON serialization;
no package was installed into the shared consumer environment. Initial helper
attempts failed on a missing PDF dependency and required settings. A sanitized
process with fresh policy-valid ephemeral settings fixed the helper setup, without
relaxing authentication validators or making a database connection.

Additional scratch artifacts under `/tmp/newsdom-mineru4-runtime-20260928`:

| Artifact | SHA-256 |
| --- | --- |
| verify_dom_projection.py | ed72d5a64d8f4e90a309a4106f1d8179b2748c67c93b19ae0e88e1bca6814b28 |
| verify_naruon_projection.py | d5970ad8c4c3c031c896ca6aceef070614fc35218580c19ac192aa00e738d629 |
| actual-supplier-dom.json | 7c5abcfd5754d6da307b7c3626529a761051385b90ebfc661e6231f81f1dc526 |
| actual-naruon-segments.json | d09f52f5278f6b030bbc66e5a6fef398a3d15ef974077e3f6da869c980871dc6 |

Naruon's runtime pin now carries this blank-page successor and the Next.js 16.3.6
security follow-up. Their combined Compose/hygiene/dependency contracts pass
27 tests with warnings as errors. The supplier GPU dependency audit remains a
separate failing legacy-runtime condition; the replay is no substitute for the
missing MinerU 4 adapter and deployment acceptance.
