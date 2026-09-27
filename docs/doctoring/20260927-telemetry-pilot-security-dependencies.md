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

## Later isolated frontend receipt

At UI integration head `71e58e5093f02e7b97874d4dcb973dc83a73f57d`, a separate detached worktree completed a frozen pnpm 11.5.3 install without the earlier dependency-resolution warnings; tracked package and lock bytes remained unchanged. Next 16.3.3 production build passed. With conflicting terminal color overrides removed from the command environment, all **443 frontend tests in 51 files passed**, and ESLint completed without warning output. Node was 24.21.0, so this is not an exact pinned-24.19.0 receipt. These later results do not convert the initial timeout or warning-bearing historical runs into green acceptance, and do not transfer to another head or prove hosted security/review acceptance.
