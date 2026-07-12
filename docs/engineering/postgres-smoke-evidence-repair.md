# PostgreSQL smoke-evidence repair — research grounding & OSMU eval

Roadmap: ContextualWisdomLab/naruon#1041 (Phase Ops). This documents
why the `@pytest.mark.postgres` smoke repair (PR that fixes #1041) is
grounded in the published flaky-test literature rather than ad-hoc, and
records the ONE-SOURCE-MULTI-USE evaluation of the reusable guard it
introduced.

## Why this is a research-grounded slice, not a chore

The 14 failures were not random breakage — every one is a textbook
instance of a **named flaky-test root cause**, and the fixes are the
**textbook remediations** for those causes. The two anchoring sources:

1. **Gruber, Lukasczyk, Kroiß & Fraser (2021).** *An Empirical Study
   of Flaky Tests in Python.* ICSE 2021 (arXiv:2101.09077). The
   canonical large-scale study of flakiness in **Python/pytest**
   specifically (22 352 PyPI projects, 876 186 tests). Headline
   finding: **Test Order Dependency causes 59%** of Python flakiness
   (vs. Java, where async-wait/concurrency dominate), and
   **Infrastructure flakiness causes 28%** — "a previously
   undocumented cause … flaky due to reasons outside the project's
   code but inside the test execution environment."
2. **Rasheed, Tahir, Dietrich, Hashemi & Zhang (2022).** *Test
   Flakiness' Causes, Detection, Impact and Responses: A Multivocal
   Review.* Journal of Systems and Software (arXiv:2212.00908). A
   651-article taxonomy consolidating Luo et al.'s seminal 10-category
   classification (async-wait, concurrency, **test-order-dependency**,
   **resource leak**, network, **time**, IO, randomness, floating
   point, unordered collections).

### Failure-class → root-cause → remediation mapping

| This PR's fix | Flaky-test root cause | Source & prescribed remediation |
|---|---|---|
| Unique `organization_id` per smoke run (was shared `"org-acme"`, count drifted as history accumulated) | **Test Order Dependency / shared external (database) state** — the dominant Python cause (59%); a *victim/polluter* pattern where rows from a prior run pollute a later run's org-scoped `COUNT` assertion | Gruber §II-A (victim/polluter/brittle/state-setter); Rasheed §4.2 "shared state … external (e.g. file system, **database**)". Fix = Rasheed Table 12 "reset state / reduce global state / run in isolation" |
| `await engine.dispose()` on all paths in `test_db.py` (leaked pooled connection → GC `ResourceWarning` failed a later test) | **Resource leak** (sub-cause of order dependency) — "code … not properly managing shared resources (obtaining a resource and not releasing it)" | Rasheed §4.2 Resource leak; Table 12 "Leak global state" |
| Missing `services: postgres` in CI (family silently skipped, rotted invisibly) | **Infrastructure flakiness / platform (Dev/Test/CI vs Production) dependency** — dev-prod parity | Gruber §II-A Infrastructure flakiness (28%); Rasheed Table 4 "Environment that the test executes in (Development/Test/CI or Production)" |
| Schema-drifted raw-SQL seeding (`emails`→`email_records`, wrong `RETURNING`, missing NOT NULL cols, asyncpg UNION casts) | **External-resource (database) dependency** — tests coupled to a real DB schema drift out of sync | Rasheed §4.2 "Reliance on external resources: **Databases**" |
| Timezone-aware `datetime.now(timezone.utc)` defaults (was `datetime.utcnow`, deprecation fatal under `PYTHONWARNINGS=error`) | **Time** category — "Relying on system time … changing UTC time" | Rasheed Table 4 Time / system date-time |
| Missing `relationship()` → FK flush ordering (`agent_run_records`→`workflow_definitions`) | **Order dependency within a single flush** — non-deterministic INSERT order over a shared FK constraint | Standards: SQLAlchemy unit-of-work orders cross-mapper INSERTs only via relationship-derived dependencies; SQL:2016 FK constraint (immediate by default) rejects the child-first order |

Gruber's central methodological warning also justifies the CI fix
directly: their whole point is that **flakiness hides unless you run
the real environment** — the `@pytest.mark.postgres` family was
skipped in CI (no Postgres service), so it degraded invisibly exactly
as their "infrastructure flakiness … only affects researchers running
large experiments" caution predicts. Test-production parity (running
CI against the same PostgreSQL engine as production) is the
twelve-factor dev/prod-parity discipline (Factor X).

### PDF archival (governance)

This sandbox's network policy blocks `arxiv.org` (proxy 403), and the
paper-access path returns text, not the PDF binary, so the PDFs could
not be committed this round — same constraint documented for the
hybrid-retrieval slice, where the repo owner later archived the PDFs
from a network-allowed session. Both papers are arXiv preprints; their
redistribution license (arXiv non-exclusive vs. CC BY) must be
confirmed before archival under `docs/research/`. Gruber 2021's FlaPy
artifact + dataset is on Zenodo (`10.5281/zenodo.4450434`). Until
confirmed CC-licensed, these stay **cite-only**.

## OSMU evaluation — the FK-relationship integrity guard

`tests/test_model_relationship_integrity.py` asserts a **model-agnostic
invariant**: every SQLAlchemy `ForeignKey` table pair must have a
`relationship()` in at least one direction, so the unit of work can
order same-flush parent/child INSERTs. This is:

- **Genuinely generic** — it reads `Base.registry.mappers` and has zero
  naruon-specific coupling; it would drop into any SQLAlchemy 2.x
  codebase unchanged. Several CWL repos use SQLAlchemy + Postgres
  (semantic-data-portal, pg-erd-cloud, keyverse), so a second consumer
  is plausible.
- **Below the extraction threshold *now*** — ~30 lines, one consumer.
  Per the 따로-또-같이 rule, extraction into a standalone
  product/submodule is justified when a **second** consumer appears.

**Product-candidate shape (when it crosses the threshold):** a small
`pytest` plugin — working name `pytest-sqlalchemy-hygiene` — bundling
this FK-relationship guard + the engine-disposal check + a
real-Postgres-parity fixture helper. For a pytest plugin the
"domain" to secure is the **PyPI name**, not a web domain. Availability
verified this session against the PyPI JSON API (`GET
pypi.org/pypi/<name>/json` → 404 = unregistered): both
**`pytest-sqlalchemy-hygiene`** and the fallback
**`pytest-sqlalchemy-integrity`** are currently unclaimed. It would
ship Apache-2.0/MIT, standalone-and-submodule, consistent with the
ecosystem's permissive-only rule. Recorded here so the candidate is
tracked; not extracted this slice (one consumer today).
