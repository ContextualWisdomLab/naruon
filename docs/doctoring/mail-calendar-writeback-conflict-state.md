# Mail-detail calendar writeback conflict state

검토 기준일: **2026-08-13**

## Incident

메일 상세의 `일정 반영`은 `/api/calendar/writeback-intent`가 If-Match 412 또는
`etag_conflict`를 반환해도 항상 `conflict_state: "none"`을 기록하고
성공 문구를 보여 주었습니다. 확정된 금요일 15:00 일정이 있는 상태에서
메일이 “지금은 금요일 15시”라고 바뀌면, 구매자는 기존 확정 일정이
덮어쓰이지 않았는지 알 수 없습니다. 이는 CP-4(확정 > 잠정)를 화면에서
깨뜨립니다.

## Decision

Writeback-intent 배치에서 가장 강한 충돌 상태를 고릅니다.

1. `provider_status === 412`, `error_code` in `{etag_conflict,
   if_match_conflict, precondition_failed, schedule_conflict}`, 또는
   status에 `conflict`가 있으면 `conflict`.
2. `requires_if_match` 또는 `if_match`만 있으면 `warning`.
3. 그 외 `none`.

`conflict`는 오류 상태로 표면화하고 원본을 덮어쓰지 않았다고 말합니다.
`warning`은 If-Match 검사가 필요하다고 말합니다. 제품 이벤트
`calendar_reflected.conflict_state`는 이 분류를 그대로 실습니다.

## Trust boundary

Naruon은 캘린더 호스트가 아닙니다. 충돌 판정은 고객 원본 계정의
CalDAV If-Match/ETag 증거에 의존합니다. 서버가 시간 창을 아직 보내지
않으므로 이 슬라이스는 기존 writeback-intent 필드를 재사용하며, 허위
시간 파싱을 추가하지 않습니다.

## Verification contract

`frontend/src/lib/calendar-writeback-conflict.test.ts`는 금요일 15:00
확정 일정의 412 배치, If-Match-only 경고, 신규 슬롯 `none`을 고정합니다.
`EmailDetail.test.tsx`는 같은 412 응답이 메일 상세에 “덮어쓰지 않았습니다”
를 표시하고 `conflict_state: "conflict"`를 기록하는지 실행합니다.

## Rollback

`EmailDetail`의 `conflict_state: "none"` 하드코딩과 기존 성공 문구로
되돌립니다. 헬퍼 모듈과 doctoring을 함께 제거합니다.

## References (APA 7th)

Daboo, C., Desruisseaux, B., & Dusseault, L. (2007). *Calendaring
extensions to WebDAV (CalDAV)* (RFC 4791). RFC Editor.
https://doi.org/10.17487/RFC4791

Fielding, R., & Reschke, J. (Eds.). (2014). *Hypertext Transfer Protocol
(HTTP/1.1): Conditional requests* (RFC 7232). RFC Editor.
https://doi.org/10.17487/RFC7232
