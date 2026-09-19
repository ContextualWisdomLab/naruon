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

Do not add a Best Practices badge image or project URL to README until
`https://www.bestpractices.dev/projects.json?url=https://github.com/ContextualWisdomLab/naruon`
returns a real project record.

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
| FLOSS license | Proprietary license text; GitHub license key `other` / SPDX `NOASSERTION` | Copyright holder — OpenSSF FLOSS license criteria stay unmet unless license policy changes |
| Governance doc | No `GOVERNANCE.md` | Maintainers — add only if governance is real |
| Independent reviewers | Collaborators: `seonghobae` only | Naruon #1371 — do not claim multi-maintainer review from inventory alone |
| Effective branch protection | Rulesets `17214772` and `18156473` each require one approving review; `17214772` also requires approval after last push; thread resolution required. Ruleset `15586698` alone is **not** the full contract. | Record integrated rules at answer time; **do not weaken** |

## Enrollment steps (external)

1. Authorized identity signs into https://www.bestpractices.dev/ via GitHub OAuth.
2. Create/claim project with repo URL `https://github.com/ContextualWisdomLab/naruon`.
3. Fill passing-level criteria from this packet and live rulesets; leave proprietary-license and other unmet items unmet with justification.
4. Record the project URL in this file and README via a reviewed PR (preserve approval rules).
5. Re-run / wait for Scorecard (central `security-scan` Scorecard job and Scorecard API) until `CII-Best-Practices` is not score 0.
6. Close alert #67 and the tracking issues only from refreshed evidence.

## README badge placeholder (do not paste until id exists)

```markdown
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/<PROJECT_ID>/badge)](https://www.bestpractices.dev/projects/<PROJECT_ID>)
```
