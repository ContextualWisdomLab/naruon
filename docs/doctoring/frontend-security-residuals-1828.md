# PR #1828 frontend security floors and remaining blockers

## Scope and pins

This dependency-only proposal is based on canonical PR #1828 at
`74f9d6dd3b34d1179ca5f2aa3c5c294d22c7d2b2`. It does not replace the PR, modify
scanner policy, introduce advisory ignores, or assert merge readiness.

Keep `vitest`, its resolved `@vitest/mocker`, and `@vitest/coverage-v8` at
`4.1.11`. Set the effective pnpm workspace overrides, the matching package
manifest overrides/resolutions, and generated lock to `brace-expansion 5.0.12`,
`js-yaml 4.3.2`, and `undici 8.10.2`. The enhanced backend pin contract checks
manifest/importer agreement, all package and snapshot versions, and actual
transitive dependency references. The Vitest upgrade necessarily updates eight
`@vitest/*` packages in tandem; the remaining three updates are isolated patch
bumps. All 568 other package records remain byte-equivalent as parsed records.

Registry availability and compatibility were verified with pnpm `11.5.3` and
Node `24.19.0`. In particular undici `8.10.2` requires Node `>=22.19.0`; do not
interpret this proposal as proof of compatibility with older Node releases.

## Historical dependency-only audit and unresolved finding

On October 3, 2026, OSV API batch queries accounted for all **580** package
records in each baseline and candidate lock, including development and optional
platform packages. The baseline had 18 package/advisory occurrences across six
affected packages (17 unique advisories). The candidate has one occurrence:

- **GHSA-vfj7-8cjw-p6xm**, high severity, `braces 3.0.3`, through
  `eslint-config-next > @next/eslint-plugin-next > fast-glob > micromatch > braces`.
  The complete pnpm audit independently reports the same remaining finding and
  exits **1**. Its claimed patched range is `>=3.0.4`, but the registry rejects
  `braces@3.0.4` and the complete published-version list ends at `3.0.3`.
  The GitHub advisory currently lists no patched version. This is an unresolved
  dependency finding, **not an exemption or a clean audit**. Upstream release or
  separately reviewed replacement/removal is needed before a clean security gate.

The requested upgrades eliminate 17 package/advisory occurrences and 16 unique
advisories in the contemporary OSV comparison, including the Vitest redirect
mock file-read finding and the undici cookie-cache disclosure finding. These are
package-version observations, not an executed exploit or production-exposure
assessment. Keep the Security Scan required gates unchanged.

Primary advisory references:

- `https://github.com/advisories/GHSA-82fw-gwwq-j7x9`
- `https://github.com/advisories/GHSA-2jfj-6hjv-fm6j`
- `https://github.com/advisories/GHSA-vfj7-8cjw-p6xm`

## Verification and strict acceptance limits

The pin regression produced real RED (six new failing cases, two existing
passing cases), followed by GREEN (eight passing cases). A fresh independent
`node_modules` install from the frozen lock succeeds offline using the proposal's
own populated pnpm store; no parent integration modules are reused.

The original dependency-only candidate passed **437 testcase assertions across
51 files** but emitted seven existing React `act(...)` warnings. Its strict test
receipt remains failed evidence. The combined owner follow-up wraps the four
mail input-event dispatches in awaited `act()` and waits for the first Calendar
source-registry load before cleanup. Both suites retain a call-through console
observer asserting that no unwrapped-act warning occurred; no diagnostic output
is suppressed. Restoring one original input dispatch makes that assertion fail.
The complete corrected frontend suite passes 437 cases without those warnings.
A diagnostic `NODE_ENV=development` run also exposed the existing CSP test's
assumption that unsafe-eval is absent; standard test mode removes that harness
mismatch without changing the assertion. Production components are unchanged.

Lint and typecheck exit zero without warning-class output. Production webpack
build succeeds with `NODE_ENV=production`, `POSTCSS_WORKERS=1`,
`DISABLE_POSTCSS_WORKERS=true`, and the existing two-worker Next configuration.
The first build reports missing-cache advice; the subsequent cached build is
clean. The first online installation had network-speed warnings; a fresh offline
frozen installation is clean. Lock regeneration emits an inherited ESLint 9
end-of-support deprecation warning. ESLint-major migration is not part of this
minimal security patch and remains a separate compatibility decision.

The historical archive and extracted JSON are different hash targets. The
archive `osv-scan-debug-11137926648.zip` matches its verified API SHA-256
`e38d1829bf5de738acd9195940de91da7eb82f2d3414e6d2f5af8e0cfc4285b2`;
its extracted `new-results.json` hashes to
`71b3f5ce73722248d7d86c4586d93d4c1423b0505951ffe23a9595759475d962`.
Comparing the JSON digest with the archive digest was an observer error, not
artifact drift. Independent baseline/candidate OSV queries remain separate
current audit evidence. Unsupported child-authored web retrieval receipts are
excluded from acceptance; source links alone are not tool retrieval receipts.

The preceding sections preserve the earlier dependency-only snapshot and failed
evidence. They do not describe the later graph or its publication state.

## Subsequent reviewed external-chain and Playwright removal

The canonical owner subsequently published `396a18fc54dd83bd9d79a6bc6bf3f1af38ba31b8`
after independent whole-PR source review. Its scoped tinyglobby replacement and
exact Next-plugin patch remove the external braces chain; its exact Playwright
1.63.0 family upgrade removes the old embedded implementation. Permanent tests
reject unsupported brace grammar and propagate non-ENOENT filesystem errors,
including the two reproduced findings from the initial adapter review.

Actual clean committed-head frozen install, dependency regressions, 437 frontend
JUnit cases, lint, typecheck, production build and unfiltered pnpm audit all
passed; the audit reported zero advisories. Vite 8.1.4 still embeds braces.
Package-audit success is not complete bundled-source clearance, and diagnostic
watch settings are not removal. Windows compatibility is not established.

The later E2E harness changes repair HttpOnly cookie fixture/header observation,
explicit server-session owner/org controls, and stale selectors without modifying
application authorization. Mocked UI and real unrouted browser transport checks
are distinct from real signed-backend/database/provider acceptance. Failed live
suite admission due to absent signing configuration remains failed evidence, not
a full E2E pass. Required current-head hosted checks, counted approval, protected
merge and released usability remain outstanding; no gate is waived.
