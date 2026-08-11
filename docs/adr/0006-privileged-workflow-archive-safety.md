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

## References

- Jerome H. Saltzer and Michael D. Schroeder, [“The Protection of Information
  in Computer Systems”](https://www.cs.virginia.edu/~evans/cs551/saltzer/),
  *Proceedings of the IEEE* 63(9) (1975). Least privilege, complete mediation,
  and separation of privilege support keeping write-capable workflow logic
  isolated from untrusted pull-request data.
- Santiago Torres-Arias et al., [“in-toto: Providing farm-to-table guarantees
  for bits and bytes”](https://www.usenix.org/conference/usenixsecurity19/presentation/torres-arias),
  *USENIX Security Symposium* (2019). The paper establishes end-to-end
  provenance for software supply chains; this supports full-SHA trusted-source
  materialization and current-head evidence.
- [OWASP Web Security Testing Guide: Test Upload of Malicious
  Files](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/10-Business_Logic_Testing/09-Test_Upload_of_Malicious_Files).
  Its archive-directory-traversal example motivates validating archive member
  paths and links before extraction. No third-party paper PDF is bundled because
  redistribution rights were not established for these sources.
