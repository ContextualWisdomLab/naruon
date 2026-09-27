---
title: "ADR-0005: Independent attachment inference"
status: "Proposed"
date: "2026-09-27"
authors: "Naruon maintainers"
tags: [architecture, attachments]
supersedes: ""
superseded_by: ""
---

# ADR-0005: Independent attachment inference

## Status

Proposed; protected integration and real PDF/provider acceptance remain open.

## Context

Story1.3 requires cited attachment facts. Recognition already commits parsed segments
and literal facts atomically, under a shared recognition sweep lease. Calling the
existing model extractor inside that transaction would retain the lease and database
resources while unrelated inference completes.

## Decision

Use a separate loop within the existing recognition worker lifecycle. A nullable
extractor-version marker on the attachment is the durable pending/completed state.
Read committed segments and the scoped provider, close that session, call the
existing extractor registry, then reopen a short write transaction. Lock the
attachment and revalidate email ownership, parent email identity and exact segment
UID/text before projecting only attachment candidates and marking completion.
Successful empty results complete the marker; absent providers and registry fallback
leave pending work. Existing fact rows are preserved, including user corrections.
Re-recognition clears the marker. Gate the loop with the existing extraction flag
and LLM/orchestrator selector. No additional service or model deadline is introduced.

## Consequences

### Positive

- **POS-001**: Recognition keeps progressing while inference is active.
- **POS-002**: Restart discovers committed attachments still awaiting inference.
- **POS-003**: Source changes reject stale writes, and inference failure preserves parsed/literal data.

### Negative

- **NEG-001**: Replicas may duplicate model calls; final row locking prevents duplicate writes.
- **NEG-002**: Each replica processes one inference at a time; sustained volume may require an existing durable job service.
- **NEG-003**: The additive column requires migration before running the updated models.

## Alternatives Considered

- **ALT-001**: Inline extraction in recognition was rejected because it holds the shared lease and transaction during inference.
- **ALT-002**: An in-memory fire-and-forget queue was rejected because restarts lose pending work and tasks can grow without bound.
- **ALT-003**: A new broker/job framework was rejected because the committed attachment and completion marker already provide durable pending state.

## Implementation Notes

- **IMP-001**: This branch stacks #1800, #1795, #1798 and #1792. Migration0019 follows filename migration0018 and has a reversible marker column.
- **IMP-002**: PostgreSQL synthetic-source tests verify session closure, source mutation rejection, completion/idempotency and fallback handling. Lifecycle and SQLite marker roundtrip tests cover stop and schema reversal. These do not prove OCR/model accuracy or deployment.
- **IMP-003**: Full reparse lineage and calibrated fact semantics remain separate acceptance work. Candidates retain inferred_unverified state.

## References

- **REF-001**: Naruon #1000 Story1.3.
- **REF-002**: Existing grounded extractor registry and attachment projection contracts in #1800/#1795.
