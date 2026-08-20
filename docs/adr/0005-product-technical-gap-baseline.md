# ADR-0005: Product and Technical Gap Baseline

- **Status:** Accepted
- **Date:** 2026-08-21
- **Scope:** Naruon product planning, PR sequencing, and procurement-readiness evidence
- **Figma File ID:** N/A — this decision adds no visual surface; existing design inventory remains authoritative.

## Decision

Naruon will maintain a single evidence-backed gap register at
[`docs/product-technical-gap-baseline.md`](../product-technical-gap-baseline.md).
The register is a planning and acceptance contract, not a claim that every
listed capability exists on protected `develop`.

Every gap implementation must identify its owning repository boundary, current
source evidence, customer-visible outcome, acceptance test, security/privacy
impact, and release or follow-up PR. The delivery loop is:

```text
current PR head → review and current checks → smallest valid fix → rerun checks
→ protected normal merge or explicit wait state → next PR or highest-value gap
```

The central ContextualWisdomLab workflows remain the owner of organization-wide
review, security, and hourly scheduling. Naruon must not copy those workflows
locally. A PR or document may refer to a queued check, but it must not call a
queued check a product defect or silently bypass it.

## Why

The existing platform plan identifies the semantic project graph as the
highest-leverage product gap because its extractor and projection path are
covered by tests but are not yet a production ingestion path. The product also
has explicit procurement gaps around live connector writeback, tenant-owner
backfill evidence, operational recovery, and attachment formats larger than
the former 1 MiB image-prefix scan. A single register prevents those gaps from
being lost across feature PRs, sibling repositories, or chat context.

## Consequences

- Product claims must link to implementation and test evidence, or state the
  missing deployment/operator prerequisite.
- A gap may be closed by Naruon, a sibling repository, or a versioned adapter;
  the register records the responsibility instead of copying sibling source.
- No Figma work is required for this documentation decision. If a future gap
  adds a new visual surface, its ADR must record the real Figma file ID and
  Storybook/design-token inventory before implementation is accepted.
- “100% coverage” is an acceptance target for supported source paths, but it
  does not turn synthetic fixtures into production evidence or authorize use of
  confidential `tests/real_datasets`.

## References (APA 7th)

International Organization for Standardization. (2023). *ISO/IEC 25010:2023
Systems and software engineering—Systems and software Quality Requirements and
Evaluation (SQuaRE)—Product quality model* (2nd ed.).
https://www.iso.org/standard/78176.html

National Institute of Standards and Technology. (2022). *Secure software
development framework (SSDF) version 1.1: Recommendations for mitigating the
risk of software vulnerabilities* (NIST Special Publication 800-218).
https://doi.org/10.6028/NIST.SP.800-218
