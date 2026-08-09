# Naruon Architecture Decision Records

This index records cross-cutting decisions that must survive beyond an individual pull request, implementation plan, or chat. `Accepted` means the decision governs architecture; it does not mean a future integration described by the ADR is already implemented on protected `develop`.

| ADR | Decision | Status |
|---|---|---|
| [ADR-0001](0001-topic-measurement-authority.md) | Structural topic measurement is a versioned TEPP model-artifact boundary, never a keyword/label heuristic | Accepted |

## Change rule

Create or update an ADR when a change moves product authority between Naruon and another CWL service, introduces a new scientific/statistical inference contract, changes persistence or tenant authority, changes model/credential trust boundaries, or replaces a fail-closed product capability with a different production owner.

Every implementing PR must keep the corresponding source, tests, doctoring, architecture/operability contract, and CHANGELOG maturity truthful. An active PR or accepted target must not be described as protected-branch implementation before it is integrated and independently verified.