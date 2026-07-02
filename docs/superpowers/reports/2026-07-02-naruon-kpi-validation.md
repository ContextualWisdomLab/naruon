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

### ROI Model And Claim Gate

The ROI model is defined for buyer-pilot measurement planning only. It separates fields that must come from live measured data from commercial assumptions that require buyer/operator approval. The current branch has no live event warehouse, payroll/cost source, contract source, or measured pilot period; therefore `estimated_period_value_krw` must not be presented as a proven value.

Formula:

```text
estimated_period_value_krw =
  time_saved_per_user_per_week_hours
  * fully_loaded_hourly_cost_krw
  * weekly_active_users
  * pilot_period_weeks
  * risk_reduction_adjustment
```

| Metric | Current value source | Current status | Allowed use |
| --- | --- | --- | --- |
| `time_saved_per_user_per_week_hours` | Live pilot task timing, before/after workflow logs, or reviewed buyer baseline | Measured value unavailable in this branch | Assumption only until pilot measurement exists |
| `fully_loaded_hourly_cost_krw` | Buyer-approved finance or HR cost model | Measured value unavailable in this branch | Assumption only, buyer-owned |
| `weekly_active_users` | Live product telemetry with workspace/user denominator rules | Measured value unavailable in this branch | Assumption only until telemetry destination is approved |
| `evidence_open_rate` | `source_chip_opened` over eligible source chips | Event contract exists; live metric unavailable | Quality/diagnostic assumption only |
| `decision_to_action_conversion_rate` | `action_item_created` after `decision_point_viewed` | Event contract exists; denominator decision pending | Quality/diagnostic assumption only |
| `pilot_period_weeks` | Signed pilot plan | Measured value unavailable in this branch | Planning input only |
| `risk_reduction_adjustment` | Buyer/operator risk review of audit, permission, and provider-write incidents | Measured value unavailable in this branch | Assumption only; cannot be used as proof |

Claim gate:

- Allowed: "Naruon has a KPI and ROI measurement framework for a controlled pilot."
- Allowed: "Live KPI and ROI evidence require a measured pilot with approved telemetry and buyer-owned cost inputs."
- Rejected: "Naruon has proven a 20B KRW ROI."
- Rejected: "Naruon is final-procurement ready based on this KPI report."
- Rejected: "The current branch contains live ROI evidence."

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
