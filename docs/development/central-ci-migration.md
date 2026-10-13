# Central CI migration

## Dependency Review

The local dependency-review workflow calls the central reusable workflow at
`58d12a9f1b46d611f75cfcf3e6c5a3fe19a55f96`. Its pull-request branch filters,
manual entrypoint, read-only permissions and concurrency are unchanged. Moderate,
high and critical findings remain blocking; the caller allows no GHSA exceptions
and disables comment summaries. The central workflow selects `CWL CI isolated`
with `self-hosted`, `linux`, `x64` and `cwlab-ci-isolated` labels and fails closed
when the exact dependency-graph comparison cannot be retrieved.

The reusable check context is `dependency-review / dependency-review`, rather
than the prior standalone context. This source change does not change branch
protection or waive the previous required context. Any effective required-context
migration must be independently verified before normal merge admission.

The caller contract resides in `backend/tests/test_dependency_review_caller.py`,
so Application CI's existing backend pytest discovery includes its trigger,
permission, concurrency and exact supplier-pin assertions.

Local contract tests and actionlint do not establish runner admission, actual
Actions execution or independent GitHub App approval. These remain incomplete
until exact-head remote results are observed. The earlier warning-bearing local
pytest run is retained separately from the warning-free strict successor.

## Remaining work

Backend, frontend and Bandit workloads still require their fixed central
suppliers and immutable caller pins. Docker validation/publication and AKS
write paths need their own isolated privileged-runner contracts. Manual mail
smoke remains on the dedicated mail-egress runner. Metadata governance is not
intrinsically GitHub-hosted-only; it needs a trusted central control supplier.
No security gate is disabled by this change.

## Sources

GitHub. (n.d.). *Reusing workflow configurations*. GitHub Docs.
https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations

GitHub. (n.d.). *Managing access to self-hosted runners using groups*. GitHub Docs.
https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/manage-access

These documentation pages were retrieved on October 13, 2026. Caller permissions
cannot be elevated by a called workflow; self-hosted availability is evaluated
in the calling repository's context. Source selection is not evidence that the
runner group has admitted that repository or executed a job.
