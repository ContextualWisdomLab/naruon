# JSON formatter current-parent adoption

This note supersedes only the dependency-parent identity and stacked-evidence statements in `json-formatter-strict-validation.md`; the formatter findings, RED/fix lineage, acceptance contract, rejected alternatives, and standards references in that document remain authoritative.

On 2026-09-16, canonical frontend dependency/security owner `ContextualWisdomLab/naruon#1623` had advanced from historical parent `17a7618eda2b212b691f08fa936e042b34258fc9` to exact `509be4c1d9b6c7ba239a108656e2382681a85341` after two PostCSS lock-integrity repairs. PR #1659 was therefore stale: its prior exact head `fbcbd5444241cd025b21d96faa8ca8130c983da9` diverged from the current parent with merge base `17a7618...` and was ten parent commits behind.

Ordinary non-force two-parent commit `71045f1bd2771863455fea11dbb1c901faa4222f` preserves `fbcbd544...` as first-parent history, adopts current #1623 `509be4c1...` as second parent, and rebuilds the tree from the current parent plus only the existing JSON formatter source, focused regression, and original strict-validation doctoring blobs. It does not copy dependency, lockfile, workflow, scanner-policy, or unrelated tool changes into this lane.

Acceptance remains evidence-bound. Parent checks or reviews do not transfer to the child. The then-current #1659 head must retain an ahead-only relationship with merge base equal to the current #1623 head, expose only the formatter-owned delta plus this traceability note, obtain trustworthy exact-base/head executable evidence through the canonical stacked-PR path, have no valid unresolved current-head finding, and receive qualifying post-last-push independent approval before merge.

The canonical stacked-workflow admission repair remains #1691. Temporary retargeting to `develop`, dummy/no-op commits, copied workflows, synthetic statuses, force-push, destructive rebase, self-approval, or dependency-owner duplication are not acceptable evidence-generation mechanisms.
