# Naruon Product Event Dictionary

This event dictionary is an instrumentation contract and local implementation record, not measured product performance. No live warehouse, dashboard, or product analytics export was available in this run. Event owner, destination, retention, and consent policy must be confirmed before these events are dispatched outside local code.

Timezone for initial dashboard cuts: `Asia/Seoul`.

Shared required fields for every event:

- `event_id`
- `occurred_at`
- `workspace_id`
- `actor_user_id`
- `surface`

Privacy rule:

- Do not send raw email body.
- Do not send raw draft body.
- Do not send raw search query text.
- Use IDs, source types, length buckets, status values, and derived metrics instead.

## Events

| Event | Owner | Trigger | Denominator grain | Entity IDs | Required additional payload | Optional payload | Quality caveat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `context_synthesis_viewed` | frontend | User opens or consumes `맥락 종합` in mail detail. | `workspace_thread` | `thread_id`, `message_id`, `ai_output_id` | `thread_id`, `message_id`, `view_state` | `ai_output_id`, `confidence`, `source_count` | Adoption only until backend synthesis request IDs and AI output IDs are joined. |
| `decision_point_viewed` | frontend | A visible `판단 포인트` card is rendered. | `ai_output` | `decision_point_id`, `ai_output_id`, `thread_id` | `decision_point_id`, `ai_output_id` | `thread_id`, `priority`, `confidence` | Conversion rates need one stable view-count rule per AI output and session. |
| `source_chip_opened` | frontend | User opens a source chip, source drawer, or original-message anchor. | `source_chip` | `source_chip_id`, `ai_output_id`, `source_id` | `source_chip_id`, `ai_output_id`, `source_id`, `source_type`, `opened_from` | none | High open rate can mean trust behavior or unclear evidence labels. |
| `action_item_created` | frontend | User confirms `실행 항목 생성`. | `action_item` | `action_item_id`, `thread_id`, `decision_point_id` | `action_item_id`, `due_date_present`, `source_backlink_present` | `thread_id`, `decision_point_id`, `assignee_type` | Creation volume needs undo/cancel and task-completion follow-through. |
| `calendar_reflected` | frontend | User confirms `일정 반영`. | `calendar_candidate` | `calendar_event_id`, `calendar_candidate_id`, `thread_id` | `calendar_candidate_id`, `conflict_state`, `provider_write_executed` | `calendar_event_id`, `thread_id` | Provider write and local intent must be separated before counting success. |
| `draft_reply_generated` | frontend | User requests `답장 초안 생성` and receives a result. | `draft_reply` | `draft_reply_id`, `thread_id`, `message_id` | `draft_reply_id`, `thread_id`, `message_id`, `instruction_present`, `generation_state` | none | Generation is not acceptance; pair with inserted, sent, edited, and discarded events. |
| `draft_reply_inserted` | frontend | Draft becomes editable content in the reply composer. | `draft_reply` | `draft_reply_id`, `thread_id`, `message_id` | `draft_reply_id`, `thread_id`, `message_id`, `insert_source` | `character_count_bucket` | Do not store body text; edit distance needs a privacy-reviewed derived metric. |
| `draft_reply_sent` | frontend | User sends or simulates sending the reviewed reply draft. | `draft_reply` | `draft_reply_id`, `thread_id`, `message_id` | `draft_reply_id`, `thread_id`, `message_id`, `send_mode` | `final_review_duration_ms` | Simulated sends must not be counted as provider-delivered replies. |
| `context_search_submitted` | frontend | User submits `맥락 검색`. | `context_search_session` | `search_session_id` | `search_session_id`, `query_length_bucket`, `filter_count` | `source_filters` | Search volume alone is weak evidence without result-open or action events. |
| `context_search_result_opened` | frontend | User opens a `맥락 검색` result detail. | `context_search_result` | `search_session_id`, `result_id` | `search_session_id`, `result_id`, `result_type`, `rank_bucket` | `confidence` | Result-open rate needs zero-result and refinement rates. |
| `context_search_result_action_created` | frontend | Search result leads to reply, task, calendar, project, approval, or policy action. | `context_search_result` | `search_session_id`, `result_id`, `action_id` | `search_session_id`, `result_id`, `action_id`, `action_type`, `source_backlink_present` | none | Comparable only after result ranking and session rules are stable. |
| `latency_guardrail_recorded` | analytics | Product-critical request or render path records latency. | `request_trace` | `request_trace_id` | `request_trace_id`, `operation`, `duration_ms`, `status` | `model_provider` | P50/P95 thresholds require baseline capture. |
| `model_quality_guardrail_recorded` | model-quality | Low-confidence, corrected, discarded, hallucination, or source-missing condition is observed. | `guardrail_evaluation` | `ai_output_id`, `guardrail_evaluation_id` | `guardrail_evaluation_id`, `ai_output_id`, `quality_signal`, `human_feedback_present` | `confidence` | Requires evaluator/audit integration before launch-readiness claims. |
| `trust_safety_guardrail_triggered` | security | Permission denial, external-share warning, policy block, or audit-sensitive action is triggered. | `guardrail_evaluation` | `guardrail_evaluation_id`, `policy_id`, `source_id` | `guardrail_evaluation_id`, `guardrail_type`, `resolution_state` | `policy_id`, `source_type` | False-positive and override reviews are required before interpreting volume as safety improvement. |

## Dashboard Grain Rules

- Context synthesis usage: numerator `context_synthesis_viewed`; denominator selected `workspace_thread` with a loaded mail detail.
- Decision-to-action conversion: numerator action events after `decision_point_viewed`; denominator `ai_output` or `decision_point` after a product decision.
- Evidence interaction: numerator `source_chip_opened`; denominator source chips attached to AI outputs.
- Context search success: numerator `context_search_result_opened` or `context_search_result_action_created`; denominator `context_search_submitted`.
- Draft reply acceptance: numerator `draft_reply_inserted` and `draft_reply_sent`; denominator `draft_reply_generated`.
- Calendar/task conversion: numerator `calendar_reflected` and `action_item_created`; denominator schedule candidates and extracted action items.

## Guardrails

- Latency: track P50/P95 by `operation`, device class, workspace, model provider, and status.
- Model quality: track low-confidence, source-missing, correction, discard, and human feedback signals by AI output.
- Trust/safety: track policy blocks, permission denials, external-share warnings, overrides, and accepted warnings.

## Implementation Pointer

The code-level contract and local no-op dispatcher live in `frontend/src/lib/product-events.ts`. Current call sites are wired in `frontend/src/components/EmailDetail.tsx` and `frontend/src/components/SearchLayout.tsx`, and the source evidence UI is implemented in `frontend/src/components/SourceDrawer.tsx`.

The dispatcher records sanitized events in memory and emits browser-local `CustomEvent("naruon:product-event")`; it does not send network analytics. External dispatch remains blocked until analytics destination, retention, consent, and warehouse ownership are confirmed.
