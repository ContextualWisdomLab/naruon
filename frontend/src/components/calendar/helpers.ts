import { calendarDefinitions } from "./constants";
import { CalendarWritebackSource, CalendarWritebackIntentResponse } from "./types";

export function buildInitialCalendarVisibility() {
  return Object.fromEntries(calendarDefinitions.map((calendar) => [calendar.id, true]));
}

export function isCustomerOwnedWritableSource(source: CalendarWritebackSource) {
  return source.writeback_enabled
    && source.protocol !== 'local'
    && source.capabilities.includes('write');
}

export function getCalendarSourceLabel(index: number) {
  return `일정 원본 ${index + 1}`;
}

export function getProtocolLabel(protocol: string) {
  switch (protocol) {
    case 'caldav':
      return 'CalDAV 원본';
    case 'carddav':
      return 'CardDAV 원본';
    case 'webdav':
      return 'WebDAV 원본';
    default:
      return '원본 계정';
  }
}

export function getCapabilityLabel(capability: string) {
  switch (capability) {
    case 'read':
      return '읽기';
    case 'write':
      return '일정 반영';
    case 'etag':
      return '충돌 검사';
    default:
      return '원본 기능';
  }
}

export function getEtagLabel(value: string | null) {
  return value ? '충돌 토큰 있음' : '충돌 토큰 대기';
}

export function getIntentProtocolLabel(protocol: string) {
  return `${getProtocolLabel(protocol)} 선택됨`;
}

export function getWritebackModeLabel(mode: CalendarWritebackIntentResponse['writeback_mode']) {
  return mode === 'customer_owned' ? '고객 원본 계정 반영' : '원본 계정 확인 필요';
}

export function getProviderExecutionLabel(result: CalendarWritebackIntentResponse) {
  if (result.provider_write_executed) return '외부 원본 쓰기 완료';
  if (result.retry_item_uid || result.status === 'queued') return '커넥터 실행 요청 접수';
  if (result.error_code) return '커넥터 실행 실패';
  return '의도만 기록';
}

export function getProviderRetryLabel(result: CalendarWritebackIntentResponse) {
  if (result.retry_item_uid || result.status === 'queued') return '재시도 대기';
  if (result.provider_write_executed) return '재시도 없음';
  return '실행 요청 없음';
}

const SEOUL_WEEKDAY: Record<string, string> = {
  Sun: "일",
  Mon: "월",
  Tue: "화",
  Wed: "수",
  Thu: "목",
  Fri: "금",
  Sat: "토",
};

function seoulDateParts(iso: string) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Seoul",
    month: "numeric",
    day: "numeric",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(new Date(iso));
  const values: Record<string, string> = {};
  for (const part of parts) {
    if (part.type !== "literal") {
      values[part.type] = part.value;
    }
  }
  return values;
}

/** Format a 회의 조율 slot from the same Seoul ISO instants used as proposal data. */
export function formatCoordinationProposalLabel(startsAt: string, endsAt: string) {
  const start = seoulDateParts(startsAt);
  const end = seoulDateParts(endsAt);
  const weekday = SEOUL_WEEKDAY[start.weekday] ?? start.weekday;
  const startHour = start.hour.padStart(2, "0");
  const startMinute = start.minute.padStart(2, "0");
  const endHour = end.hour.padStart(2, "0");
  const endMinute = end.minute.padStart(2, "0");
  return `${start.month}월 ${start.day}일 (${weekday}) ${startHour}:${startMinute} - ${endHour}:${endMinute}`;
}

/** Format the calendar chrome month from the shared YYYY-MM display month. */
export function formatCalendarDisplayMonth(month: string) {
  const [year, monthNumber] = month.split("-");
  return `${year}년 ${Number(monthNumber)}월`;
}

export function getApiErrorStatus(error: unknown) {
  const shapedError = error as { status?: unknown; response?: { status?: unknown } } | null;
  if (typeof shapedError?.status === 'number') return shapedError.status;
  if (typeof shapedError?.response?.status === 'number') return shapedError.response.status;
  return null;
}