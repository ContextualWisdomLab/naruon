# ADR-0006: Consume Noema and model orchestration through owner contracts

**Status:** Proposed

**Date:** 2026-09-04

**Decision owner:** Naruon maintainers

**Scope:** Naruon's workspace-agent integration boundary

## Context

Naruon owns workspace-agent tools, tenant and workspace authorization, and the
mail, calendar, task, and knowledge-graph domain rules those tools invoke. The
same product name also appears in `ContextualWisdomLab/noema`, whose protected
`main` currently defines Noema as an evidence-producing credential and
maintenance control plane for governed GitHub automation.

The repositories compose, but neither may infer a shared runtime from a shared
name. Noema's protected contract says provider discovery and routing belong to
`ContextualWisdomLab/contextual-orchestrator`; model-backed Noema jobs consume
its published gateway contract and reject direct-provider fallback. A proposed
`noema-core` package exists only on draft Noema PR #536. It is not a released
dependency and does not prove a Naruon adoption contract.

Naruon PRs #1384 and #1486 remain draft, independently active consumer lanes.
They must not copy an owner's source, consume an owner's branch, or transfer
review and check evidence between heads.

Contextual Orchestrator PR #1004 is the active owner repair for structured
output recovery across distinct eligible candidates. It remains an open
candidate, so Naruon may use its contract as dependency planning evidence but
must not treat its branch implementation as released runtime behavior.

## Decision

1. Naruon retains ownership of workspace-agent prompts, tools, domain policy,
   tenant/workspace authorization, audit behavior, and user-facing outcomes.
2. Provider-neutral model discovery and routing are consumed only through a
   released `contextual-orchestrator` API and tenant/workspace-authorized
   credential boundary. Naruon does not silently fall back to a direct provider.
3. Noema credential, GitHub review, and maintenance capabilities are consumed
   only through Noema's released contracts. Naruon does not import Noema owner
   source or read its database.
4. The proposed `noema-core` package is not adopted until its owner PR merges,
   an immutable release is published, and Naruon verifies a versioned contract.
   Shared construction code alone does not move Naruon domain logic into Noema.
5. Quarantine execution remains a separately published isolation capability;
   this ADR does not assign it to Naruon or fold it into workspace-agent code.

## Consequences

- PR #1384 is the Naruon routing lane and must fail closed when the released
  orchestrator contract is unavailable.
- PR #1486 may add Naruon-owned calendar policy as a workspace-agent tool, but
  it cannot establish a second model-routing authority.
- Noema PR #536 is upstream proposed evidence only. A later Naruon adoption PR
  must pin a released version and add contract tests at the consumer boundary.
- Contextual Orchestrator PR #1004 must merge and publish an immutable contract
  before Naruon claims malformed structured-output recovery through that path.
- Earlier PR #1527 remains historical investigation evidence; this ADR replaces
  its contradictory separate-runtime/shared-runtime conclusions with the live
  owner/consumer boundary.

## Alternatives considered

### Treat all Noema-named code as one bounded context

Rejected. The protected owner contract describes a GitHub automation control
plane, while Naruon owns workspace-agent domain behavior. A common name is not
a versioned interoperability contract.

### Permanently separate every implementation detail

Rejected. This would also forbid legitimate consumption of released owner
contracts. Reuse is allowed at published API/package boundaries after release
and conformance evidence exist.

### Consume draft owner branches directly

Rejected. Draft heads are mutable, carry no immutable release identity, and
cannot transfer their checks or approvals to a consumer.

## Evidence and references

- `ContextualWisdomLab/noema`, protected `main` README, verified 2026-09-04.
- `ContextualWisdomLab/noema` PR #536, draft proposal for `noema-core`, verified
  2026-09-04.
- `ContextualWisdomLab/naruon` PRs #1384, #1486, and #1527, verified 2026-09-04.
- `ContextualWisdomLab/contextual-orchestrator` PR #1004, exact head
  `6a992538b6efcc34b957f72fc599bb33ac40c152`, verified 2026-09-04.
- Evans, E. (2003). *Domain-driven design: Tackling complexity in the heart of
  software*. Addison-Wesley.
- Vernon, V. (2013). *Implementing domain-driven design*. Addison-Wesley.
