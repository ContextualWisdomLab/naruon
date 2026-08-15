# GitHub Actions registry audit

## Status and authority boundary

This document describes the **active PR implementation** for issue #1324. It is
not protected-`develop` shipped truth until its pull request lands. The detector
is intentionally **read-only**: it classifies GitHub Actions workflow identities
and produces evidence for a separately authorized operator. It does not grant or
exercise workflow-disable authority.

Do not restore historical bootstrap/finalizer YAML merely to manage a stale
Actions registry record. Do not add a repository token, PAT, broad inherited
secret, or temporary self-modifying workflow to make this detector operational.

## Why repository contents are insufficient

Deleting a workflow file removes it from the Git tree but does not by itself
prove that the corresponding Actions workflow identity is absent or disabled in
the GitHub control plane. A defensible inventory therefore compares two
independently fetched surfaces:

1. the paginated Actions workflow registry; and
2. the exact recursive Git tree for one protected default-branch commit.

GitHub's workflow-list endpoint exposes each workflow's `id`, `name`, `path`, and
`state`, and paginates at at most 100 records per page. GitHub's recursive-tree
endpoint exposes a `truncated` flag; when it is true the tree cannot prove path
absence and the audit must fail closed.

## Evidence algorithm

`backend/services/github_actions_registry_audit.py` applies the following
sequence without mutating GitHub:

1. Resolve the current default branch and its exact commit SHA.
2. Fetch a recursive tree bound to that SHA. Abort on a truncated tree.
3. Fetch workflow-registry pages at 100 records per page until the advertised
   `total_count` is reached.
4. Abort on a moving `total_count`, an empty intermediate page, an observed count
   greater than `total_count`, or a duplicate workflow ID.
5. Classify repository-path records by **exact path membership**, never by a
   workflow's display name.
6. Treat case variants, percent-encoded paths, traversal segments, backslashes,
   duplicate separators, NUL-bearing strings, and an empty workflow suffix as
   unresolved rather than mutation-safe evidence.
7. Optionally compare with a previous receipt. If the same workflow ID now
   points to a different exact path, abort with `workflow_id_path_changed`; a new
   workflow ID is not confused with a reused identity.
8. Refetch the default-branch SHA after collection. Abort if it moved.
9. Persist or otherwise retain the receipt before any separately authorized
   remediation action.

## Classifications

| Classification | Meaning | Operator implication |
| --- | --- | --- |
| `present_repository_workflow` | Exact registry path exists in the bound Git tree. | Preserve unless a separate reviewed change intentionally removes it. |
| `active_orphan_repository_workflow` | Canonical repository workflow path is absent from the bound tree while registry state is `active`. | Candidate for independent operator review; classification alone is not disable authority. |
| `disabled_orphan_repository_workflow` | Canonical repository workflow path is absent and registry state is not `active`. | Retain as historical evidence; no disable action is needed from this detector. |
| `dynamic_or_external_workflow` | Registry path is outside `.github/workflows/`. | Do not infer repository ownership; investigate the GitHub-owned/dynamic source separately. |
| `unresolved_workflow_record` | Path resembles a repository workflow but is non-canonical or ambiguous. | Fail closed; no mutation may rely on this record. |

## Receipt requirements

A usable receipt records, at minimum:

- repository;
- protected default-branch name and exact SHA;
- offset-bearing observation time;
- registry `total_count` and observed record count;
- every pagination receipt with page number, item count, and page-advertised
  total;
- every workflow ID, name, exact path, state, and classification.

The exact default-branch SHA is an evidence boundary. If the branch moves during
collection, discard the incomplete observation and start a fresh audit rather
than relabelling stale evidence as current.

## Failure reasons

The detector uses stable machine-readable reasons so recurrence and operator
systems can distinguish evidence failure from a clean audit:

- `default_branch_tree_truncated`;
- `workflow_registry_pagination_incomplete`;
- `workflow_registry_total_changed`;
- `workflow_registry_count_exceeded`;
- `duplicate_workflow_id`;
- `default_branch_moved`;
- `previous_receipt_repository_mismatch`;
- `workflow_id_path_changed`.

Control-plane adapters may additionally raise explicit API failure reasons such
as permission denial, resource disappearance, or transient service failure.
Those conditions are non-passing evidence and must not be converted into a clean
result.

## Operator remediation protocol

After a clean read-only receipt identifies an active orphan candidate, the
operator must refetch the exact default-branch SHA, current registry record, and
current repository tree immediately before any control-plane mutation. Confirm
that the workflow ID/path pair is unchanged and that the path remains absent.
Preserve supported CI, security, review, deployment, release, and maintenance
workflows. If any identity, path, tree, permission, or branch evidence changed,
stop that lane and reacquire evidence.

After an authorized disable operation, collect a second complete receipt and
prove both conditions together: the target orphan is no longer active and all
supported repository workflows remain present/operational. The before/after
receipts are the acquisition-diligence and incident-response evidence; a name-
only screenshot or a deleted YAML file is not equivalent evidence.

## Current incident observation

During development of this slice on 2026-08-16, the live Actions registry
reported `total_count = 128`, while the protected `develop` tree at
`bc98789521d21271e84789888413c182aa111b4d` contained a much smaller supported
workflow set. This is **development-time incident evidence**, not a permanent
repository invariant. Recompute both surfaces for every future decision; never
hard-code `128` or that SHA into production classification logic.

## Verification

Focused regression suites:

```text
backend/tests/test_github_actions_registry_audit.py
backend/tests/test_github_actions_registry_continuity.py
backend/tests/test_github_actions_registry_new_identity.py
```

They cover complete pagination, partial pagination, moving totals, duplicate IDs,
truncated trees, default-branch movement, explicit 403/404/5xx-style adapter
failures, hostile path variants, legitimate finalizer-like names, ID/path reuse,
repository-mismatched prior receipts, and genuinely new workflow identities.
Exact-head repository CI/security/review gates remain authoritative for merge.

## References

GitHub, Inc. (2026). *REST API endpoints for workflows* (API version
2026-03-10). GitHub Docs. https://docs.github.com/en/rest/actions/workflows?apiVersion=2026-03-10

GitHub, Inc. (2026). *REST API endpoints for Git trees* (API version
2026-03-10). GitHub Docs. https://docs.github.com/en/rest/git/trees?apiVersion=2026-03-10
