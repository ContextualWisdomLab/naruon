# OpenSSF Best Practices enrollment (Naruon)

Status: **not enrolled**. This document is an evidence packet for an authorized
representative. It does not assert a badge tier or project id.

Tracking:

- AppGuardrail issue [#309](https://github.com/ContextualWisdomLab/appguardrail/issues/309)
- Naruon issue [#1178](https://github.com/ContextualWisdomLab/naruon/issues/1178)
- Org tracker [ContextualWisdomLab/.github#694](https://github.com/ContextualWisdomLab/.github/issues/694)
- Code-scanning alert [#67](https://github.com/ContextualWisdomLab/naruon/security/code-scanning/67) (`CIIBestPracticesID`)

## Rule

Do not fabricate OpenSSF Best Practices attestations. Answer only from live
repository and organization evidence. Leave unmet criteria unmet.

The OpenSSF Best Practices program is for FLOSS projects. The Passing level
requires every MUST and MUST NOT criterion to be met, including
`floss_license` ("The software produced by the project MUST be released as
FLOSS"). Naruon's current proprietary license is therefore a **hard blocker to
a Passing badge**, not an engineering criterion that can be waived with a
justification. Only an authorized copyright-holder/legal/business licensing
decision can change this boundary. Primary criteria:
https://www.bestpractices.dev/en/criteria?details=true&rationale=true

Do not add a Best Practices badge image or project URL to README until
`https://www.bestpractices.dev/projects.json?url=https://github.com/ContextualWisdomLab/naruon`
returns a real project record. Do not claim Passing until the live project
record satisfies every required criterion.

## Live gap (re-check before enrollment)

As of the companion handoff dated 2026-09-19:

- bestpractices.dev project count for this repo URL: **0**
- Published Scorecard `CII-Best-Practices`: **0**
- Alert #67: **open**

## Evidence that already exists

| Topic | Evidence |
| --- | --- |
| Public repository | `https://github.com/ContextualWisdomLab/naruon` (default branch `develop`) |
| Security policy | `SECURITY.md` (private vulnerability reporting + `security@naruon.net`) |
| Contribution process | `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` |
| CI on PRs / default branch | `.github/workflows/app-ci.yml`, `bandit.yml`, plus org-required workflows from `ContextualWisdomLab/.github` (`security-scan.yml` includes Scorecard soft upload, CodeQL PR, Strix, Semgrep, OpenCode review, merge scheduler) |
| Dependency updates | `.github/dependabot.yml` |
| Dependency review | org-required path via central `security-scan.yml` (repo-local duplicate intentionally removed) |
| Releases | GitHub Releases (example: `v0.14.4`) |
| Changelog | `CHANGELOG.md` |

## Known unmet or constrained criteria (disclose honestly)

| Topic | Current fact | Owner / remediation |
| --- | --- | --- |
| FLOSS license | Proprietary license text; GitHub license key `other` / SPDX `NOASSERTION`; OpenSSF Passing requires `floss_license` MUST to be met | Copyright holder / legal / business decision. No engineering ETA or waiver exists; a qualifying FLOSS or dual-license path must be explicitly authorized before Passing can be claimed |
| Governance doc | No `GOVERNANCE.md` | Maintainers — add only if governance is real |
| Independent reviewers | Collaborators: `seonghobae` only | Naruon #1371 — do not claim multi-maintainer review from inventory alone |
| Effective branch protection | Rulesets `17214772` and `18156473` each require one approving review; `17214772` also requires approval after last push; both require review-thread resolution. Ruleset `15586698` alone is **not** the full contract. | Record integrated rules at answer time; **do not weaken** |

## Enrollment steps (external)

1. Authorized identity signs into https://www.bestpractices.dev/ via GitHub OAuth.
2. Create/claim a project with repo URL `https://github.com/ContextualWisdomLab/naruon` only if the organization wants an explicit program record; project creation by itself is not a Passing badge.
3. Fill criteria strictly from this packet and live repository/ruleset evidence. Record the proprietary-license condition as a hard Passing blocker; do not mark `floss_license` met or treat it as waivable.
4. If an authorized licensing decision makes Naruon eligible, refresh every MUST/MUST NOT criterion before pursuing Passing. Otherwise keep the project record non-Passing and do not publish a badge.
5. Record a real project URL in this file and README only after it exists, via a reviewed PR that preserves the effective approval rules.
6. Re-run / wait for Scorecard (central `security-scan` Scorecard job and Scorecard API) and verify `CII-Best-Practices` against the actual program record rather than assuming project creation closes the finding.
7. Close alert #67 and the tracking issues only from refreshed evidence that satisfies their acceptance criteria; an unresolved legal licensing blocker remains open.

## README badge placeholder (do not paste until id exists)

```markdown
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/<PROJECT_ID>/badge)](https://www.bestpractices.dev/projects/<PROJECT_ID>)
```
