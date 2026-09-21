# Dependabot bounded version-update groups

## Problem

The protected `develop` configuration grouped every Python and frontend npm version update with `patterns: ["*"]` and no SemVer boundary. On 2026-09-21 that policy produced three direct-to-`develop` aggregate PRs from the same protected base:

- #1749 `backend-python` at `944e0ac13d9837ba7e8ac11e762a649e9c36cf7b`: 76 updates in four backend dependency files, including the security-material `aiosmtplib 5.1.2 -> 5.1.3` change together with framework, migration, observability and LLM-client changes.
- #1750 `frontend-npm` at `8b0a79bdd39700764270c6235bcc07dd874332ac`: 19 updates in `frontend/package.json` and `frontend/pnpm-lock.yaml`, combining the current Next.js security-owner delta with React 19.3 and Vitest 5 changes.
- #1751 `ci-python` at `1d30f606fde72aa8ec141ab4553d2a09e91d46cc`: 104 updates across backend, connector and CI requirement inputs, including `strix-agent`, model/provider clients and unrelated runtime libraries.

Those PRs are mechanically generated correctly, but the grouping policy makes compatibility risk, security urgency and canonical ownership inseparable. A security patch can be delayed by unrelated major/minor migrations, while a broad GREEN result would not identify which owner contract actually changed.

GitHub documents that wildcard groups may create large PRs and supports `applies-to`, `patterns`/`exclude-patterns`, and `update-types` to keep groups bounded by update class. Major and minor releases outside a group's `update-types` continue as independent PRs rather than being silently ignored.

## Decision

Keep the existing weekly cadence and package-ecosystem boundaries. Change only the three wildcard application/runtime groups:

- `backend-python`: group version-update patches only; exclude `aiosmtplib` so its current SMTP command-injection hardening remains independently reviewable.
- `ci-python`: group version-update patches only. Strix, provider/client and other minor/major changes therefore remain individually attributable.
- `frontend-npm`: group version-update patches only. Next.js, React, Vitest and other minor/major compatibility changes therefore do not share one generated owner lane.

GitHub Actions and Docker image groups are unchanged because this finding was reproduced in application/runtime dependency groups, not in those ecosystems. Security-update grouping is also not broadened here; `applies-to: version-updates` makes the intended scope explicit.

## Executable contract and evidence

The RED commit `9935b1d6140a20cb54300810290e5769d576cf1a` adds `backend/tests/test_dependabot_grouping_contract.py`. Against the protected configuration it requires keys that do not exist: `applies-to`, patch-only `update-types`, and the `aiosmtplib` exclusion. That is an executable configuration RED rather than a prose-only finding.

The causal configuration fix is `c27a8c0ef391845393b1a87b0fe4bed361bdf569`. It does not edit generated lockfiles, dependency versions, current Dependabot branches, branch protection or workflow gates. Existing generated PRs remain provenance and must be repaired or routed independently; this policy only prevents the same mixed-risk grouping from being regenerated after it reaches protected ancestry.

Repository-local and hosted tests have not yet been claimed for these commits. Acceptance requires the exact integrated head to parse the YAML, run the focused contract under the normal backend test environment, pass current required workflows/security checks and receive qualifying independent review. A future Dependabot cycle is the operational acceptance check: minor/major updates must appear outside the wildcard patch groups, and `aiosmtplib` must not be swallowed by `backend-python`.

## Rejected alternatives

Keeping `patterns: ["*"]` for every SemVer level preserves fewer PRs but reproduces cross-owner mega-PRs and couples urgent fixes to unrelated migrations. Disabling major/minor updates would reduce noise by hiding useful updates, so it is rejected. Hard-coding every package into a large domain taxonomy was also rejected in this repair because ownership changes over time; patch-only grouping plus explicit security-material exclusion is the smallest policy that removes the reproduced failure without inventing a new dependency ontology.

## References

GitHub. (2026). *Dependabot options reference*. GitHub Docs. https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference

GitHub. (2026). *Optimizing the creation of pull requests for Dependabot version updates*. GitHub Docs. https://docs.github.com/en/code-security/tutorials/secure-your-dependencies/optimizing-pr-creation-version-updates

aiosmtplib maintainers. (2026). *aiosmtplib v5.1.3* [Software release]. GitHub. https://github.com/cole/aiosmtplib/releases/tag/v5.1.3
