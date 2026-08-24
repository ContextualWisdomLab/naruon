export type ProductEventOwner =
  | "frontend"
  | "backend"
  | "analytics"
  | "security"
  | "model-quality";

export type ProductEventPrivacyClass =
  | "metadata"
  | "pseudonymous"
  | "sensitive-context-reference";

export type ProductEventDenominatorGrain =
  | "workspace_thread"
  | "ai_output"
  | "source_chip"
  | "decision_point"
  | "action_item"
  | "calendar_candidate"
  | "draft_reply"
  | "context_search_session"
  | "context_search_result"
  | "request_trace"
  | "guardrail_evaluation";

export const PRODUCT_EVENT_TIMEZONE = "Asia/Seoul";

export const PRODUCT_EVENT_NAMES = [
  "context_synthesis_viewed",
  "decision_point_viewed",
  "source_chip_opened",
  "action_item_created",
  "calendar_reflected",
  "draft_reply_generated",
  "draft_reply_inserted",
  "draft_reply_sent",
  "context_search_submitted",
  "context_search_result_opened",
  "context_search_result_action_created",
  "latency_guardrail_recorded",
  "model_quality_guardrail_recorded",
  "trust_safety_guardrail_triggered",
] as const;

export type ProductEventName = (typeof PRODUCT_EVENT_NAMES)[number];

export interface ProductEventField {
  name: string;
  required: boolean;
  description: string;
}

export interface ProductEventContract {
  owner: ProductEventOwner;
  trigger: string;
  denominatorGrain: ProductEventDenominatorGrain;
  timezone: typeof PRODUCT_EVENT_TIMEZONE;
  privacyClass: ProductEventPrivacyClass;
  entityIds: string[];
  payloadFields: ProductEventField[];
  qualityCaveat: string;
}

export type ProductEventPayloadValue = string | number | boolean | null | undefined;
export type ProductEventPayload = Record<string, ProductEventPayloadValue>;

export interface RecordedProductEvent {
  name: ProductEventName;
  payload: Record<string, string | number | boolean | null>;
}

const BASE_FIELDS: ProductEventField[] = [
  {
    name: "event_id",
    required: true,
    description: "Unique event UUID generated client-side or server-side before dispatch.",
  },
  {
    name: "occurred_at",
    required: true,
    description: `ISO-8601 timestamp interpreted for dashboard cuts in ${PRODUCT_EVENT_TIMEZONE}.`,
  },
  {
    name: "workspace_id",
    required: true,
    description: "Workspace scope for denominator isolation.",
  },
  {
    name: "actor_user_id",
    required: true,
    description: "Pseudonymous user identifier; do not send email addresses.",
  },
  {
    name: "surface",
    required: true,
    description: "UI surface such as mail_detail, context_search, calendar, or task.",
  },
];

function fields(...fields: ProductEventField[]): ProductEventField[] {
  return [...BASE_FIELDS, ...fields];
}

export const PRODUCT_EVENT_CONTRACTS: Record<ProductEventName, ProductEventContract> = {
  context_synthesis_viewed: {
    owner: "frontend",
    trigger: "The user opens or consumes the mail-detail `맥락 종합` card for a selected thread.",
    denominatorGrain: "workspace_thread",
    timezone: PRODUCT_EVENT_TIMEZONE,
    privacyClass: "sensitive-context-reference",
    entityIds: ["thread_id", "message_id", "ai_output_id"],
    payloadFields: fields(
      { name: "thread_id", required: true, description: "Stable source thread identifier." },
      { name: "message_id", required: true, description: "Selected message identifier." },
      { name: "ai_output_id", required: false, description: "Identifier for the synthesis response when available." },
      { name: "confidence", required: false, description: "Normalized 0-100 confidence value shown to the user." },
      { name: "source_count", required: false, description: "Number of evidence sources bound to the synthesis." },
      { name: "view_state", required: true, description: "loaded, loading, empty, or error." },
    ),
    qualityCaveat: "Counts are adoption signals only until backend synthesis request IDs and AI output IDs are joined.",
  },
  decision_point_viewed: {
    owner: "frontend",
    trigger: "A visible `판단 포인트` or decision-oriented card is rendered for a selected thread or result.",
    denominatorGrain: "ai_output",
    timezone: PRODUCT_EVENT_TIMEZONE,
    privacyClass: "sensitive-context-reference",
    entityIds: ["decision_point_id", "ai_output_id", "thread_id"],
    payloadFields: fields(
      { name: "decision_point_id", required: true, description: "Stable ID for one decision point within the AI output." },
      { name: "ai_output_id", required: true, description: "AI response ID that produced the decision point." },
      { name: "thread_id", required: false, description: "Source thread if the decision came from mail detail." },
      { name: "priority", required: false, description: "Product severity or priority bucket." },
      { name: "confidence", required: false, description: "Normalized 0-100 confidence value shown to the user." },
    ),
    qualityCaveat: "Do not compare conversion rates until one view-count rule is selected per AI output and session.",
  },
  source_chip_opened: {
    owner: "frontend",
    trigger: "The user opens a source chip, evidence drawer, or original-message anchor before accepting AI output.",
    denominatorGrain: "source_chip",
    timezone: PRODUCT_EVENT_TIMEZONE,
    privacyClass: "sensitive-context-reference",
    entityIds: ["source_chip_id", "ai_output_id", "source_id"],
    payloadFields: fields(
      { name: "source_chip_id", required: true, description: "UI source-chip identifier." },
      { name: "ai_output_id", required: true, description: "AI response that cited the source." },
      { name: "source_id", required: true, description: "Email, attachment, document, calendar, or task source ID." },
      { name: "source_type", required: true, description: "mail, attachment, document, calendar, task, project, or audit." },
      { name: "opened_from", required: true, description: "synthesis_card, decision_point_card, drawer, or search_result." },
    ),
    qualityCaveat: "High open rate can indicate trust behavior or unclear evidence labels; interpret with correction/discard rates.",
  },
  action_item_created: {
    owner: "frontend",
    trigger: "The user confirms `실행 항목 생성` from a decision point, todo extraction, or context search result.",
    denominatorGrain: "action_item",
    timezone: PRODUCT_EVENT_TIMEZONE,
    privacyClass: "sensitive-context-reference",
    entityIds: ["action_item_id", "thread_id", "decision_point_id"],
    payloadFields: fields(
      { name: "action_item_id", required: true, description: "Created task/action identifier." },
      { name: "thread_id", required: false, description: "Source thread when created from mail detail." },
      { name: "decision_point_id", required: false, description: "Decision point that led to the action item." },
      { name: "assignee_type", required: false, description: "self, teammate, team, or unassigned." },
      { name: "due_date_present", required: true, description: "Whether a due date or schedule candidate exists." },
      { name: "source_backlink_present", required: true, description: "Whether the created action links back to its source." },
    ),
    qualityCaveat: "Creation volume is incomplete without undo/cancel and task-completion follow-through.",
  },
  calendar_reflected: {
    owner: "frontend",
    trigger: "The user confirms `일정 반영` from an extracted schedule candidate or action item.",
    denominatorGrain: "calendar_candidate",
    timezone: PRODUCT_EVENT_TIMEZONE,
    privacyClass: "sensitive-context-reference",
    entityIds: ["calendar_event_id", "calendar_candidate_id", "thread_id"],
    payloadFields: fields(
      { name: "calendar_candidate_id", required: true, description: "Candidate schedule identifier." },
      { name: "calendar_event_id", required: false, description: "Provider event ID or local intent ID after confirmation." },
      { name: "thread_id", required: false, description: "Source mail thread if available." },
      { name: "conflict_state", required: true, description: "none, warning, conflict, or override." },
      { name: "provider_write_executed", required: true, description: "Whether the provider write executed or only an intent was recorded." },
      { name: "calendar_batch_status", required: false, description: "success, intent-only, partial, or error for a multi-intent calendar request." },
      { name: "calendar_intent_count", required: false, description: "Number of calendar writeback intents in the batch." },
      { name: "calendar_provider_write_count", required: false, description: "Number of calendar intents whose provider write executed." },
    ),
    qualityCaveat: "Provider write and local intent must be separated before treating this as successful calendar creation.",
  },
  draft_reply_generated: {
    owner: "frontend",
    trigger: "The user requests `답장 초안 생성` and a draft response is returned.",
    denominatorGrain: "draft_reply",
    timezone: PRODUCT_EVENT_TIMEZONE,
    privacyClass: "sensitive-context-reference",
    entityIds: ["draft_reply_id", "thread_id", "message_id"],
    payloadFields: fields(
      { name: "draft_reply_id", required: true, description: "Draft generation identifier." },
      { name: "thread_id", required: true, description: "Source thread for the draft." },
      { name: "message_id", required: true, description: "Selected message that anchors the reply." },
      { name: "instruction_present", required: true, description: "Whether the user supplied a draft instruction." },
      { name: "generation_state", required: true, description: "success or error." },
    ),
    qualityCaveat: "Generation alone is not acceptance; pair with inserted, sent, edited, and discarded events.",
  },
  draft_reply_inserted: {
    owner: "frontend",
    trigger: "A generated or pasted `답장 초안` becomes editable content in the reply composer.",
    denominatorGrain: "draft_reply",
    timezone: PRODUCT_EVENT_TIMEZONE,
    privacyClass: "sensitive-context-reference",
    entityIds: ["draft_reply_id", "thread_id", "message_id"],
    payloadFields: fields(
      { name: "draft_reply_id", required: true, description: "Draft identifier carried from generation or manual insertion." },
      { name: "thread_id", required: true, description: "Source thread for the draft." },
      { name: "message_id", required: true, description: "Selected message that anchors the reply." },
      { name: "insert_source", required: true, description: "generated, manual, template, or restored." },
      { name: "character_count_bucket", required: false, description: "Length bucket only; do not send draft body text." },
    ),
    qualityCaveat: "Do not store body text in product analytics; edit-distance needs a privacy-reviewed derived metric.",
  },
  draft_reply_sent: {
    owner: "frontend",
    trigger: "The user sends or simulates sending a reply that came through the draft-review flow.",
    denominatorGrain: "draft_reply",
    timezone: PRODUCT_EVENT_TIMEZONE,
    privacyClass: "sensitive-context-reference",
    entityIds: ["draft_reply_id", "thread_id", "message_id"],
    payloadFields: fields(
      { name: "draft_reply_id", required: true, description: "Draft identifier tied to the sent reply." },
      { name: "thread_id", required: true, description: "Source thread for the reply." },
      { name: "message_id", required: true, description: "Selected message that anchors the reply." },
      { name: "send_mode", required: true, description: "simulated or provider_send." },
      { name: "final_review_duration_ms", required: false, description: "Time between insertion and send, when available." },
    ),
    qualityCaveat: "Simulated sends must not be counted as provider-delivered replies in launch dashboards.",
  },
  context_search_submitted: {
    owner: "frontend",
    trigger: "The user submits a `맥락 검색` query.",
    denominatorGrain: "context_search_session",
    timezone: PRODUCT_EVENT_TIMEZONE,
    privacyClass: "sensitive-context-reference",
    entityIds: ["search_session_id"],
    payloadFields: fields(
      { name: "search_session_id", required: true, description: "Stable ID for a single search session." },
      { name: "query_length_bucket", required: true, description: "Length bucket only; do not send query text." },
      { name: "filter_count", required: true, description: "Number of active source/date/person/attachment filters." },
      { name: "source_filters", required: false, description: "Allowed source-type labels only, not raw source names." },
    ),
    qualityCaveat: "Search success requires downstream result-open or action events; query volume alone is weak evidence.",
  },
  context_search_result_opened: {
    owner: "frontend",
    trigger: "The user opens a result detail from `맥락 검색`.",
    denominatorGrain: "context_search_result",
    timezone: PRODUCT_EVENT_TIMEZONE,
    privacyClass: "sensitive-context-reference",
    entityIds: ["search_session_id", "result_id"],
    payloadFields: fields(
      { name: "search_session_id", required: true, description: "Search session that produced the result." },
      { name: "result_id", required: true, description: "Stable result identifier." },
      { name: "result_type", required: true, description: "mail, document, person, calendar, task, project, or timeline." },
      { name: "rank_bucket", required: true, description: "top_1, top_3, top_10, or below_10." },
      { name: "confidence", required: false, description: "Normalized 0-100 relevance or confidence value shown to the user." },
    ),
    qualityCaveat: "Result-open rate should be read with zero-result and refinement rates to avoid rewarding noisy ranking.",
  },
  context_search_result_action_created: {
    owner: "frontend",
    trigger: "A result detail leads to a reply, task, calendar, project, approval, or policy action.",
    denominatorGrain: "context_search_result",
    timezone: PRODUCT_EVENT_TIMEZONE,
    privacyClass: "sensitive-context-reference",
    entityIds: ["search_session_id", "result_id", "action_id"],
    payloadFields: fields(
      { name: "search_session_id", required: true, description: "Search session that produced the result." },
      { name: "result_id", required: true, description: "Result that led to the action." },
      { name: "action_id", required: true, description: "Created downstream action identifier." },
      { name: "action_type", required: true, description: "reply, task, calendar, project, approval, policy, or relation_capture." },
      { name: "source_backlink_present", required: true, description: "Whether the downstream action links back to the result." },
    ),
    qualityCaveat: "Action-created conversion is only comparable after result ranking and session rules are stable.",
  },
  latency_guardrail_recorded: {
    owner: "analytics",
    trigger: "A product-critical request or render path records latency for synthesis, search, draft, calendar, or task actions.",
    denominatorGrain: "request_trace",
    timezone: PRODUCT_EVENT_TIMEZONE,
    privacyClass: "metadata",
    entityIds: ["request_trace_id"],
    payloadFields: fields(
      { name: "request_trace_id", required: true, description: "Trace or request ID shared across frontend and backend logs." },
      { name: "operation", required: true, description: "synthesis, search, draft_reply, calendar_reflection, or task_creation." },
      { name: "duration_ms", required: true, description: "End-to-end latency in milliseconds." },
      { name: "status", required: true, description: "success, error, timeout, cancelled, or abandoned." },
      { name: "model_provider", required: false, description: "Provider label when a model call is part of the operation." },
    ),
    qualityCaveat: "P50/P95 thresholds require baseline capture; do not set launch gates from this contract alone.",
  },
  model_quality_guardrail_recorded: {
    owner: "model-quality",
    trigger: "A low-confidence, corrected, discarded, hallucination, or source-missing condition is observed.",
    denominatorGrain: "guardrail_evaluation",
    timezone: PRODUCT_EVENT_TIMEZONE,
    privacyClass: "sensitive-context-reference",
    entityIds: ["ai_output_id", "guardrail_evaluation_id"],
    payloadFields: fields(
      { name: "guardrail_evaluation_id", required: true, description: "Quality evaluation identifier." },
      { name: "ai_output_id", required: true, description: "AI output under evaluation." },
      { name: "quality_signal", required: true, description: "low_confidence, corrected, discarded, hallucination, or source_missing." },
      { name: "confidence", required: false, description: "Normalized 0-100 confidence value shown to the user." },
      { name: "human_feedback_present", required: true, description: "Whether a user correction or feedback action exists." },
    ),
    qualityCaveat: "Requires evaluator/audit integration before it can support launch-readiness claims.",
  },
  trust_safety_guardrail_triggered: {
    owner: "security",
    trigger: "A permission denial, external-share warning, policy block, or audit-sensitive action is triggered.",
    denominatorGrain: "guardrail_evaluation",
    timezone: PRODUCT_EVENT_TIMEZONE,
    privacyClass: "sensitive-context-reference",
    entityIds: ["guardrail_evaluation_id", "policy_id", "source_id"],
    payloadFields: fields(
      { name: "guardrail_evaluation_id", required: true, description: "Trust/safety evaluation identifier." },
      { name: "guardrail_type", required: true, description: "permission_denied, external_share_warning, policy_block, or audit_required." },
      { name: "policy_id", required: false, description: "Policy identifier when a policy caused the guardrail." },
      { name: "source_type", required: false, description: "Source type involved in the decision." },
      { name: "resolution_state", required: true, description: "blocked, overridden, accepted_warning, or dismissed." },
    ),
    qualityCaveat: "False-positive and override reviews are required before interpreting guardrail volume as safety improvement.",
  },
};

export function isProductEventName(value: string): value is ProductEventName {
  return (PRODUCT_EVENT_NAMES as readonly string[]).includes(value);
}

export function getProductEventContract(name: ProductEventName): ProductEventContract {
  return PRODUCT_EVENT_CONTRACTS[name];
}

const BLOCKED_PAYLOAD_FIELD_NAMES = new Set([
  "body",
  "email_body",
  "draft",
  "draft_body",
  "query",
  "raw_query",
  "search_query",
]);

const localProductEventBuffer: RecordedProductEvent[] = [];
const LOCAL_PRODUCT_EVENT_BUFFER_LIMIT = 200;

export function createProductEventId(prefix = "product_evt"): string {
  const secureRandom = globalThis.crypto;
  if (!secureRandom) {
    throw new Error("Web Crypto is required for product event identifiers");
  }
  if (typeof secureRandom.randomUUID === "function") {
    return `${prefix}_${secureRandom.randomUUID()}`;
  }
  const bytes = new Uint8Array(16);
  secureRandom.getRandomValues(bytes);
  const randomId = Array.from(bytes, (value) =>
    value.toString(16).padStart(2, "0"),
  ).join("");
  return `${prefix}_${randomId}`;
}

export function bucketTextLength(value: string): "empty" | "1_20" | "21_80" | "81_200" | "201_plus" {
  const length = value.trim().length;
  if (length === 0) return "empty";
  if (length <= 20) return "1_20";
  if (length <= 80) return "21_80";
  if (length <= 200) return "81_200";
  return "201_plus";
}

export function bucketSearchRank(index: number): "top_1" | "top_3" | "top_10" | "below_10" {
  if (index <= 0) return "top_1";
  if (index < 3) return "top_3";
  if (index < 10) return "top_10";
  return "below_10";
}

function sanitizeProductEventPayload(name: ProductEventName, payload: ProductEventPayload) {
  const contract = PRODUCT_EVENT_CONTRACTS[name];
  const allowedFields = new Set(contract.payloadFields.map((field) => field.name));
  const sanitized: Record<string, string | number | boolean | null> = {};

  Object.entries(payload).forEach(([fieldName, value]) => {
    const normalizedFieldName = fieldName.toLowerCase();
    if (BLOCKED_PAYLOAD_FIELD_NAMES.has(normalizedFieldName)) {
      throw new Error(`Product event payload field is blocked: ${fieldName}`);
    }
    if (!allowedFields.has(fieldName)) {
      throw new Error(`Product event payload field is not in the ${name} contract: ${fieldName}`);
    }
    if (value === undefined) return;
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean" || value === null) {
      sanitized[fieldName] = value;
    }
  });

  if (!sanitized.event_id) sanitized.event_id = createProductEventId(name);
  if (!sanitized.occurred_at) sanitized.occurred_at = new Date().toISOString();
  if (!sanitized.workspace_id) sanitized.workspace_id = "local";
  if (!sanitized.actor_user_id) sanitized.actor_user_id = "anonymous";
  if (!sanitized.surface) sanitized.surface = "unknown";

  const missingPayloadFields = contract.payloadFields
    .filter((field) => field.required && sanitized[field.name] === undefined)
    .map((field) => field.name);
  if (missingPayloadFields.length > 0) {
    throw new Error(`Product event payload missing required fields for ${name}: ${missingPayloadFields.join(", ")}`);
  }

  return sanitized;
}

export function recordProductEvent(name: ProductEventName, payload: ProductEventPayload): RecordedProductEvent {
  const event: RecordedProductEvent = {
    name,
    payload: sanitizeProductEventPayload(name, payload),
  };

  localProductEventBuffer.push(event);
  if (localProductEventBuffer.length > LOCAL_PRODUCT_EVENT_BUFFER_LIMIT) {
    localProductEventBuffer.shift();
  }

  if (typeof window !== "undefined" && typeof window.dispatchEvent === "function") {
    window.dispatchEvent(new CustomEvent("naruon:product-event", { detail: event }));
  }

  return event;
}

export function getRecordedProductEvents(): RecordedProductEvent[] {
  return [...localProductEventBuffer];
}

export function clearRecordedProductEvents() {
  localProductEventBuffer.length = 0;
}
