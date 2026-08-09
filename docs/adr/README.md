# Naruon Architecture Decision Records

This index records cross-cutting decisions that must survive beyond an individual pull request, implementation plan, or chat. `Accepted` means the decision governs architecture; it does not mean a future integration described by the ADR is already implemented on protected `develop`.

| ADR | Decision | Status |
|---|---|---|
| [ADR-0001](0001-topic-measurement-authority.md) | Naruon-local policy for consuming structural topic measurement, never a keyword/label heuristic | Accepted |

## Change rule

Create or update an ADR when a Naruon change adopts or declines an external service contract, introduces a new scientific/statistical inference contract, changes persistence or tenant authority, changes model/credential trust boundaries, or replaces a fail-closed product capability with a different production dependency. A Naruon ADR records Naruon's decision only; it cannot assign authority to, or accept a decision for, another service.

Every implementing PR must keep the corresponding source, tests, doctoring, architecture/operability contract, and CHANGELOG maturity truthful. An active PR or accepted target must not be described as protected-branch implementation before it is integrated and independently verified.
