/** Classify mail-to-calendar writeback intents by schedule-conflict evidence. */

export type CalendarWritebackConflictState = "none" | "warning" | "conflict";

export type CalendarWritebackConflictIntent = {
  requires_if_match?: boolean;
  if_match?: string | null;
  status?: string | null;
  error_code?: string | null;
  provider_status?: number | null;
};

const CONFLICT_ERROR_CODES = new Set([
  "etag_conflict",
  "if_match_conflict",
  "precondition_failed",
  "schedule_conflict",
]);

/**
 * Return the strongest conflict state across one writeback-intent batch.
 *
 * A 412 / explicit conflict error is `conflict` (do not overwrite a confirmed
 * commitment). An If-Match token without an error is `warning` (existing
 * event, fail closed until the human confirms). Otherwise `none`.
 */
export function calendarWritebackConflictState(
  intents: readonly CalendarWritebackConflictIntent[],
): CalendarWritebackConflictState {
  let sawWarning = false;
  for (const intent of intents) {
    const errorCode = (intent.error_code || "").trim().toLowerCase();
    const status = (intent.status || "").trim().toLowerCase();
    if (
      intent.provider_status === 412 ||
      CONFLICT_ERROR_CODES.has(errorCode) ||
      status.includes("conflict")
    ) {
      return "conflict";
    }
    if (intent.requires_if_match || Boolean(intent.if_match)) {
      sawWarning = true;
    }
  }
  return sawWarning ? "warning" : "none";
}

/** Return action-item labels whose paired writeback intent is a hard conflict. */
export function calendarWritebackBlockedSummaries(
  intents: readonly CalendarWritebackConflictIntent[],
  summaries: readonly string[],
): string[] {
  const blocked: string[] = [];
  for (let index = 0; index < intents.length; index += 1) {
    const intent = intents[index];
    if (calendarWritebackConflictState([intent]) !== "conflict") {
      continue;
    }
    const summary = (summaries[index] || "").trim();
    if (summary) {
      blocked.push(summary);
    }
  }
  return blocked;
}

/** Return the mail-detail status copy for one classified writeback batch. */
export function calendarWritebackConflictMessage(
  state: CalendarWritebackConflictState,
  intentCount: number,
  blockedSummaries: readonly string[] = [],
): string {
  if (state === "conflict") {
    const blockedLabel = (blockedSummaries[0] || "").trim();
    if (blockedLabel) {
      return `기존 확정 일정과 충돌이 있어 ‘${blockedLabel}’을 덮어쓰지 않았습니다.`;
    }
    return "기존 확정 일정과 충돌이 있어 원본을 덮어쓰지 않았습니다.";
  }
  if (state === "warning") {
    return `${intentCount}개 일정 반영 의도를 요청했습니다. 기존 일정 If-Match 검사가 필요합니다.`;
  }
  return `${intentCount}개 일정 반영 의도를 선택한 원본 계정에 요청했습니다.`;
}
