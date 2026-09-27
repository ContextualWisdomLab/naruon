# Telemetry pilot dependency security repair

Observed 2026-09-27 11:14 UTC. The Trivy failure on [PR #1772](https://github.com/ContextualWisdomLab/naruon/pull/1772) also reproduces on its clean `develop` baseline `042b0c70531b229af3acbd0421a2f23098d848b3`; it is inherited rather than introduced by telemetry.

The baseline has six findings: AnyIO CVE-2026-63374, CVE-2026-63349, CVE-2026-64847; Next.js CVE-2026-75604 and GHSA-2xp9-vwfh-vxw4; sharp GHSA-rgj7-g3m4-5g8c. Update the uv lock to AnyIO 4.14.2, Next.js and its ESLint config to 16.3.3, and the existing sharp override to 0.35.4. Runtime hash requirements already select AnyIO 4.14.2. Regenerate locks with existing package managers; keep security scanners and exclusions unchanged.

Primary patch evidence: [AnyIO TLS advisory](https://github.com/agronholm/anyio/security/advisories/GHSA-82r6-8w77-94w6), [AnyIO process advisory](https://github.com/agronholm/anyio/security/advisories/GHSA-3w57-8xmc-8v26), [Next.js advisory](https://github.com/vercel/next.js/security/advisories/GHSA-2xp9-vwfh-vxw4), [sharp advisory](https://github.com/lovell/sharp/security/advisories/GHSA-rgj7-g3m4-5g8c).

## Reproduce

Run in each clean checkout with the same refreshed Trivy database:

```sh
trivy image --download-db-only
trivy fs --scanners vuln --format json --output /tmp/naruon-vulnerabilities.json .
```

Trivy 0.74.0 reports six vulnerabilities on the baseline and zero on the repaired tree. This is local dependency evidence, not proof of the hosted secret/misconfiguration scans or independent review. Frozen pnpm install succeeds; 69 focused backend tests pass with `PYTHONWARNINGS=error`; frontend lint and typecheck pass. Node 24.19.0 is pinned in mise, matching the existing CI major, and Python stays in the backend-local uv environment.

Frontend tests: initial concurrent build/test invocation timed out in one existing 5-second UI test (436 passed). With the same unchanged timeouts and code, the repeat passes all 437 tests in 51 files. Do not interpret the first invocation as green. Lock resolution also emitted registry latency and pre-existing ESLint 9 deprecation warnings; the subsequent frozen install completed successfully.

## Pilot database lifecycle regression

At 2026-09-27 12:57 UTC, the pilot's new startup configuration query exposed pooled PostgreSQL connections surviving application shutdown. Consecutive application lifespans then reused connections from a closed event loop; the mixed observability tests failed with connection cleanup warnings under Python 3.14.6 and `PYTHONWARNINGS=error`. The same tests passed on the clean `042b0c70531b229af3acbd0421a2f23098d848b3` baseline (19 tests), so this regression belongs to the pilot rather than the inherited dependency repair.

Dispose the primary and read-only pools at application shutdown after workers and telemetry stop, including when the served scope raises. Keep normal connection pooling during service operation. This follows [SQLAlchemy's async engine lifecycle contract](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-multiple-asyncio-event-loops). The unchanged real PostgreSQL connector-history smoke test passes in isolation; the repaired combined observability/application suite also passes against a task-owned PostgreSQL 18.4 container. This proves the local database path, not production SIEM delivery or a hosted approval. The regression check covers exceptional scope exit and both pool disposals.
