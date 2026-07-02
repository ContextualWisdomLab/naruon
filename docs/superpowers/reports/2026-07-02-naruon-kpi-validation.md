# Validation Report

Question being answered: whether the Naruon KPI and measurement framework in `docs/superpowers/specs/2026-07-02-naruon-figma-product-design-analytics-design.md` is accurate, well-supported, and ready to share as a product analytics handoff.

Data sources and as-of date:

- Repo evidence as of checked commit `00e9c15f559349d21fdf53bffc6c487c323dd4be` on `develop`.
- Design source evidence from `docs/ui-ux/README.md`, `docs/ui-ux/naruon-ui-ux-mapping.md`, mockups, reference sources, and manifests.
- No live event warehouse, product analytics table, dashboard, or telemetry export was available in this run.

### Overall Assessment: Share with caveats

The KPI framework is suitable for stakeholder discussion and instrumentation planning. It is not suitable for performance claims, target-setting, or launch-readiness decisions until live telemetry exists.

### Methodology Review

The analysis answers the product question implied by the design package: how to measure whether Naruon moves users from fragmented email context to evidence-backed judgment and execution. The metrics map cleanly to the first vertical slice: thread selected, `맥락 종합` consumed, source evidence opened, `판단 포인트` reviewed, and execution action created.

Definitions are directionally sound, but event names and logging destinations are assumptions. The framework avoids causal claims and explicitly marks targets as provisional.

### Issues Found

1. Severity: Medium. Live analytics schema and destination are not confirmed.
   Evidence: the repo now contains a local event contract and dispatcher in `frontend/src/lib/product-events.ts`, with call sites in `EmailDetail.tsx` and `SearchLayout.tsx`, but no live warehouse, dashboard, or export destination was available for validation.
   Impact: engineering can validate local UI instrumentation, but dashboards still cannot be launched without confirming owner, retention, consent, warehouse schema, and transport.

2. Severity: Medium. Denominators need product decisions before implementation.
   Evidence: conversion metrics need stable denominator rules, such as whether a `판단 포인트` view counts once per user, thread, session, or AI output.
   Impact: adoption and conversion rates can drift or become non-comparable across teams if denominator grain is not locked.

3. Severity: Low. Guardrails are defined but not thresholded.
   Evidence: latency, model quality, and trust/safety are named, but alert thresholds and acceptable baselines are not known.
   Impact: the framework can guide instrumentation, but not operational go/no-go decisions yet.

### Calculation Spot-Checks

- Context synthesis usage: Locally instrumented in mail detail; not verified as a live metric because no event table exists.
- Decision-to-action conversion: Task creation is locally instrumented; no live conversion table exists.
- Evidence interaction: Source drawer opening is locally instrumented; backend AI output/source lineage still needs durable provenance IDs.
- Context search success: Search submit, result open, and relation-capture action are locally instrumented; no live session table exists.
- Draft reply acceptance: Generated, inserted, and sent events are locally instrumented; discard and privacy-reviewed edit-distance metrics are not implemented.
- Calendar/task conversion: Calendar reflection and task creation are locally instrumented; no provider-success dashboard exists.
- Model quality: Not verified - evaluator output and correction feedback are not available.
- Latency: Not verified - frontend timing and backend trace linkage are not available.
- Trust/safety: Not verified - audit/security event integration is not available.

### Visualization Review

No live dashboard or chart exists. The recommended dashboard cuts in the spec are presentation-ready as a dashboard brief, but not validated as rendered visuals.

### Suggested Improvements

1. Add an event dictionary with event name, owner, trigger, entity IDs, timestamp timezone, required payload fields, and privacy classification.
2. Define denominator grain for each rate: user-thread, workspace-thread, AI output, search session, draft, schedule candidate, or action item.
3. Add guardrail thresholds after 2-4 weeks of baseline capture: P50/P95 latency, error rate, low-confidence rate, source-missing rate, discard rate, and undo rate.
4. Add dashboard acceptance checks: date range, timezone, workspace filters, device filters, and sample-size suppression for small segments.

### Required Caveats for Stakeholders

- No KPI value in this package is measured product performance.
- All event names and targets are provisional until telemetry owner and destination are confirmed.
- Conversion rates must not be compared across teams or periods until denominator grain and timezone rules are locked.
- Model quality and trust/safety guardrails require evaluator/audit integration before launch-readiness decisions.
