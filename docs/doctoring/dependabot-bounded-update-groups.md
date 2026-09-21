# Dependabot bounded version-update groups

## Problem

The protected `develop` configuration grouped every Python and frontend npm version update with `patterns: ["*"]` and no SemVer boundary. On 2026-09-21 that policy produced three direct-to-`develop` aggregate PRs from the same protected base:

- #1749 `backend-python` at `944e0ac13d9837ba7e8ac11e762a649e9c36cf7b`: 76 updates in four backend dependency files, including the security-material `aiosmtplib 5.1.2 -> 5.1.3` change together with framework, migration, observability and LLM-client changes.
- #1750 `frontend-npm` at `8b0a79bdd39700764270c6235bcc07dd874332ac`: 19 updates in `frontend/package.json` and `frontend/pnpm-lock.yaml`, combining the current Next.js security-owner delta with React 19.3 and Vitest 5 changes.
- #1751 `ci-python` at `1d30f606fde72aa8ec141ab4553d2a09e91d46cc`: 104 updates across backend, connector and root CI requirement inputs, including `strix-agent`, model/provider clients and unrelated runtime libraries.

Those PRs are mechanically generated correctly, but the grouping policy makes compatibility risk, security urgency and canonical ownership inseparable. A security patch can be delayed by unrelated major/minor migrations, while a broad GREEN result would not identify which owner contract actually changed.

The first repair bounded the three wildcard groups to version-update patches and excluded `aiosmtplib` from the backend bulk group. A fresh owner-boundary review then found that this was not sufficient for root `ci-python`: #1751's actual changed-file inventory contains `backend/requirements-agent.txt`, `backend/requirements-hashes.txt`, `backend/requirements.txt`, `connector/requirements-hashes.txt`, `connector/requirements.txt`, and three root CI/Strix requirement files. The root `pip` entry therefore crosses the separately configured `/backend` and `/connector` dependency trees before grouping is even considered.

GitHub documents both parts of the repair contract. `groups.update-types` can restrict a group to `patch`, `minor`, or `major`, with unmatched update levels remaining eligible for separate pull requests. `exclude-paths` removes matching files or directories from the update scan for one package-ecosystem entry, and paths are relative to that entry's configured `directory`.

## Decision

Keep the existing schedules and package-ecosystem entries, but bound both update class and manifest ownership:

- `backend-python`: group version-update patches only; exclude `aiosmtplib` so its current SMTP command-injection hardening remains independently reviewable.
- root `ci-python`: group version-update patches only **and** exclude `backend/**` and `connector/**` from the root `pip` scan. Backend dependency files stay with the dedicated `/backend` entry; connector dependency files stay with the dedicated `/connector` entry.
- `frontend-npm`: group version-update patches only. Next.js, React, Vitest and other minor/major compatibility changes therefore do not share one generated owner lane.

GitHub Actions and Docker image groups are unchanged because this reproduced finding concerns the application/runtime Python/npm update entries. Security-update grouping is also not broadened here; `applies-to: version-updates` makes the intended scope explicit.

## Executable contract and evidence

The first RED commit `9935b1d6140a20cb54300810290e5769d576cf1a` added `backend/tests/test_dependabot_grouping_contract.py`. Against protected configuration it required explicit version-update scope, patch-only `update-types`, and the `aiosmtplib` exclusion. The first causal fix `c27a8c0ef391845393b1a87b0fe4bed361bdf569` implemented those constraints.

The second RED commit `a689777c96a5bf6986f55252b8004915480c4416` captures the remaining cross-owner scan defect. It requires the root `pip` update stanza to exclude both `backend/**` and `connector/**`; the preceding #1752 head has neither key and therefore cannot satisfy that contract. The causal fix `6a5ead0173bf9b8daaf95b364c3a819f0495de05` adds exactly those two `exclude-paths` and leaves the dedicated `/backend` and `/connector` entries intact.

Neither repair edits generated lockfiles, dependency versions, current Dependabot branches, branch protection or workflow gates. Existing generated PRs remain provenance/migration lanes and must be reconciled independently. The policy prevents the reproduced mixed-risk and cross-owner grouping only after this exact source reaches protected ancestry.

A direct repository checkout is unavailable in the current execution environment because `github.com` DNS resolution fails there, so no local/container PASS is claimed. Acceptance requires the exact integrated head to parse the YAML, run the focused contract under the normal backend test environment, pass current required workflows/security checks and receive qualifying independent post-last-push review. A later Dependabot cycle is the operational acceptance check: minor/major updates stay outside wildcard patch groups, `aiosmtplib` is not swallowed by `backend-python`, and root `ci-python` no longer changes files under `backend/` or `connector/`.

## Rejected alternatives

Keeping `patterns: ["*"]` for every SemVer level preserves fewer PRs but reproduces cross-owner mega-PRs and couples urgent fixes to unrelated migrations. Disabling major/minor updates would reduce noise by hiding useful updates, so it is rejected. Leaving the root `pip` scanner recursive and relying on grouping alone is also rejected because #1751 proves that manifest discovery can cross the dedicated backend/connector owner boundaries before SemVer grouping applies. Removing the root entry would stop maintenance of root CI/Strix requirement inputs, while moving those inputs into backend or connector would create a false owner. Explicit root-relative exclusions are the smallest causal boundary.

Hard-coding every package into a large domain taxonomy remains out of scope because ownership changes over time; path ownership plus patch-only grouping and the one reproduced security-material exclusion resolve the observed failure without inventing a dependency ontology.

## References

GitHub. (2026). *Dependabot options reference*. GitHub Docs. https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference

GitHub. (2026). *Optimizing the creation of pull requests for Dependabot version updates*. GitHub Docs. https://docs.github.com/en/code-security/tutorials/secure-your-dependencies/optimizing-pr-creation-version-updates

aiosmtplib maintainers. (2026). *aiosmtplib v5.1.3* [Software release]. GitHub. https://github.com/cole/aiosmtplib/releases/tag/v5.1.3