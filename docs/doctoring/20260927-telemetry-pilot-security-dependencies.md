# Telemetry pilot dependency security repair

Observed 2026-09-27 11:14 UTC. The Trivy failure on [PR #1772](https://github.com/ContextualWisdomLab/naruon/pull/1772) also reproduces on its clean `develop` baseline `042b0c70531b229af3acbd0421a2f23098d848b3`; it is inherited rather than introduced by telemetry.

The baseline has six findings: AnyIO CVE-2026-63374, CVE-2026-63349, CVE-2026-64847; Next.js CVE-2026-75604 and GHSA-2xp9-vwfh-vxw4; sharp GHSA-rgj7-g3m4-5g8c. The initial repair selected AnyIO 4.14.2, Next.js and its ESLint config 16.3.3, and sharp 0.35.4. The current follow-up raises Next.js and its ESLint config to 16.3.6; the earlier scan alone does not establish coverage of the newer advisory. Runtime hash requirements already select AnyIO 4.14.2. Regenerate locks with existing package managers; keep security scanners and exclusions unchanged.

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

## Advisory-specific follow-up, 2026-09-28

[GHSA-vcvr-r3jv-pc5j](https://github.com/vercel/next.js/security/advisories/GHSA-vcvr-r3jv-pc5j)
affects Next.js `>=16.2.0,<16.3.6`; the primary advisory identifies 16.3.6 as
patched. No `next/og` or `ImageResponse` usage was found in current frontend
source. Reachable exploitation is not established, but 16.3.3 is an affected
dependency and is replaced by the exact 16.3.6 pin and its regenerated lock.

Trivy 0.74.0's database refresh command completed, retaining the current database
(updated 2026-09-27 07:04:17 UTC, next update 2026-09-28 07:04:17 UTC).
Database SHA-256: `41fbf7b3a54777919084a8afc6cf0954760c0286298fd3cd2a6c29d668d2d643`.
Metadata SHA-256: `59bc0d81ccac9645a9bc4b04e5926f692b21410be896b56d457f2db696513560`.
Both the isolated 16.3.3 baseline manifests and the 16.3.6 candidate return zero
vulnerabilities under that same database. Therefore the zero result does not
prove coverage of this advisory; patch evidence comes from the primary advisory
and exact resolved version, independently of the scanner's coverage gap.
The candidate scan confirms its Next.js package record is 16.3.6.

A regression contract checks stable exact Next.js 16 pins at least 16.3.6 and
matching root-importer/package records for both Next.js and its ESLint config.
It fails on the initial 16.3.3 tree and passes after the update. Both dependency
pin contracts pass with warnings as errors, and frozen pnpm 11.5.3 install
succeeds in a new isolated worktree. Local Node is 24.21.0; the repository's
24.19.0 pin has not been verified in this environment. Hosted acceptance remains
separate from these local checks.

Local frontend verification on the candidate: lint/typecheck completed without diagnostics; the initial default-worker run had 435 passes and two unchanged 5-second timeouts. The two-worker repeat passes all 437 tests in 51 files with the same assertions and timeouts. The Next.js 16.3.6 production build exits zero and generates all 16 pages. This is local Node 24.21.0 evidence, not pinned-node or protected hosted acceptance.
