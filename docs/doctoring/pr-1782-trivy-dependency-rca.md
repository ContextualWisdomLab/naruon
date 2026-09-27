# PR #1782 Trivy dependency RCA

## Status

- **PR:** [ContextualWisdomLab/naruon#1782](https://github.com/ContextualWisdomLab/naruon/pull/1782)
- **Failing head:** `d156f6b286b520f5cc93fa66f4fc079cfa6a46a1`
- **Failing workflow:** Security Scan run
  [`36248648092`](https://github.com/ContextualWisdomLab/naruon/actions/runs/36248648092),
  job `108483221378`
- **Disposition:** source repair prepared; the PR remains Draft until the repair's
  exact-head hosted Security Scan reaches a terminal successful conclusion.

## Failure evidence

The Trivy job read the generated dependency locks and reported six actionable
advisories. The backend `uv.lock` contained AnyIO `4.14.1`, while the frontend
pnpm lock resolved Next.js `16.2.12` and Sharp `0.35.0`:

| Locked dependency | Findings | Severity |
| --- | --- | --- |
| AnyIO | `CVE-2026-63374`, `CVE-2026-63349`, `CVE-2026-64847` | Critical, High, Medium |
| Next.js | `CVE-2026-75604`, `GHSA-2xp9-vwfh-vxw4` | Critical, Critical |
| Sharp | `GHSA-rgj7-g3m4-5g8c` | High |

This was a product dependency defect, not stale predecessor evidence, a
provider transient, or a reason to suppress the gate. The repository has
independently generated uv, hashed-requirements, and pnpm locks, but it lacked
a regression contract binding the versions remediated in this run across all
of those artifacts. In particular, the hashed requirements had already moved
to AnyIO `4.14.2`, while `uv.lock` remained on `4.14.1`; neither version met the
current fixed floor.

## Repair

The RED regression test
`test_trivy_dependency_security_floors_match_all_generated_locks` first failed
against the vulnerable locks. The smallest source repair then:

- updates AnyIO to `4.15.1` in `uv.lock` and the hash-pinned requirements;
- updates Next.js and `eslint-config-next` together to `16.3.6`;
- updates the pnpm Sharp override and lock resolution to `0.35.4`; and
- makes the regression test verify the source declarations, importers,
  package records, snapshots, uv lock, and hashed requirements together.

An ESLint 10 trial was rejected after the real lint command failed inside
`eslint-plugin-react@7.37.5` (`contextOrFilename.getFilename is not a
function`). The branch therefore retains ESLint 9 without peer-dependency
exceptions; dependency admission was not weakened to conceal the upstream
compatibility gap.

## Local verification

The repaired tree produced the following evidence before publication:

- backend: `1807 passed, 33 skipped` with `PYTHONWARNINGS=error` and proxy
  environment variables removed so the local harness does not inject an
  undeclared SOCKS transport;
- frontend: `51` files and `437` tests passed;
- ESLint, TypeScript, and the Next.js `16.3.6` production build passed; and
- frozen uv and pnpm installs resolved the repaired locks.

These local results are not a substitute for hosted exact-head evidence. A
new commit must cause the ordinary Security Scan to evaluate the new head;
only that current-head terminal result may close this RCA.
