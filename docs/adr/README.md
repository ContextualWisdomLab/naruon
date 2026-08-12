# Naruon Architecture Decision Records

Status values: Proposed, Accepted, Superseded.

This index records durable Naruon architectural decisions. A decision is not shipped behavior merely because its ADR exists. `Accepted` requires protected-branch implementation or process authority plus current verification evidence.

| ADR | Status | Decision |
|---|---|---|
| [0001](0001-inkspan-backed-llm-email-writing-guidance.md) | Proposed | Inkspan-backed, LLM-native email writing guidance with fast-mlsirm judge calibration and no keyword semantic fallback |

## Decision discipline

- **Proposed:** design and ownership boundaries are documented, but implementation or operational acceptance evidence is incomplete.
- **Accepted:** protected `develop` contains the governing implementation or process and its tests, security evidence, documentation, and rollback contract are current.
- **Superseded:** retained for traceability but replaced by a later ADR.

Material changes to model authority, editor ownership, keyword/heuristic fallback, PII handling, send gating, calibration, persistence, or cross-repository integration require a new or superseding ADR rather than silent edits.

## Required ADR sections

Every material ADR records context, alternatives, decision, consequences, failure and recovery, security and privacy, accessibility where applicable, compatibility and migration, verification, research/standards traceability, and rollback or supersession conditions.
