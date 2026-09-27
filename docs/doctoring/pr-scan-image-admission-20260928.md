# PR scan and image admission recovery

## Scope and existing owners

Protected `develop@042b0c70531b229af3acbd0421a2f23098d848b3` has no workflow-level
concurrency for Bandit or Docker validation. On 2026-09-27 UTC, Naruon #1799
run 36320119655 (Bandit) and 36320119770 (Docker) remained queued at original
head `3597dd03232d945b79b2a9e0cda2288e501e9fb1`, while the PR head was already
`25ed23b94385518549323dd88680909a7b15af84`. These are `pull_request` events;
the top-level run SHA is the immutable target identity. The PR association's
head SHA now points to the latest head and must not replace that run identity.

Reuse canonical Bandit source and its test from #1562 at
`cdef60348a7da793a24828ec3d2a1bd6cc680f02`; reuse Docker source and both test
deltas from #1592 at `b2ee42b6e9286aac4b908a644f472c71d9ccc2a6`.
#1606 at `c1286c1631365862e2b576fb045388796d3bd246` is provenance-only and
has zero effective delta, so it is not a usable concurrency implementation.

This integration carries only the two workflow admission contracts and their
three test surfaces. It does not claim complete succession of #1562's 49-file
scope, close either owner PR, change their branches or transfer their approvals.
Bandit preserves manual, push and rerun identities while coalescing first PR
attempts; Docker isolates manual reruns and tag publication from first PR
attempts. Workflow scope permits coalescing before runner admission.

## Verification

Existing-owner source/tests reused rather than a new concurrency abstraction.
Both affected workflows pass actionlint. All 37 concurrency and release
contracts pass with warnings as errors, pytest plugin autoload disabled and
only the installed asyncio plugin explicitly loaded; no backend conftest or
real datasets are accessed. The initial configuration omitted that plugin and
had one config warning, retained as a separate receipt rather than described
as warning-free. Ruff and diff checks pass.

Historical runs retain their original workflow definitions; adoption does not
prove they were cancelled. Cleanup is restricted to #1799/#1802 first-attempt
`pull_request` Bandit/Docker runs with a freshly verified differing live head,
and accepted cancellations require terminal `completed/cancelled` proof.
Protected hosted acceptance remains separate from these local contracts.
