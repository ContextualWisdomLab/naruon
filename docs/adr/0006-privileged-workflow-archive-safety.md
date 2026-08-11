# ADR-0006: Safe materialization for privileged workflow gates

- Status: Accepted
- Date: 2026-08-11

## Context

`pull_request_target` and central required workflows have write-capable
metadata or status permissions. They must execute only trusted workflow logic,
even when the event carries an untrusted pull request head. A tarball is a
convenient immutable-base transport, but a generic archive extraction step can
permit path traversal or link-based writes if its assumptions change.

## Decision

- Materialize governance code only from a full commit SHA resolved from the
  trusted base or a live PR base. The PR head is data for current-head evidence,
  never the privileged gate implementation.
- Validate every archive member before extraction: reject absolute paths,
  parent-directory components, symbolic links, hard links, device entries, and
  any resolved target outside the temporary workspace.
- Require the materialized governance script to exist as a regular file before
  executing it. Privileged jobs do not checkout or execute untrusted PR code,
  and third-party Actions remain pinned to full commit SHAs.
- Treat scanner failures as findings or wait states according to their explicit
  gate contract; do not hide a hard scan failure with a generic continuation or
  bypass branch protection.

## Consequences

- A malformed or unexpectedly structured trusted archive fails closed before
  any write-capable gate logic runs.
- Current-head review, Checks, and merge decisions stay separate from the
  trusted implementation that evaluates them.
- A central workflow repository remains the authority for organization-wide
  OpenCode, Strix, and merge-scheduler behavior; Naruon records and verifies
  the contract but does not silently fork or mutate that external source.
