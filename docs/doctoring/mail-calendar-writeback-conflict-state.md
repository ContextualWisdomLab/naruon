# Mail-detail calendar writeback conflict state

검토 기준일: **2026-08-15**

## Incident and scope

메일 상세는 `/api/calendar/writeback-intent` 응답에 If-Match 412 또는
`etag_conflict` 증거가 포함될 때도 이를 `conflict_state: "none"`으로
분류하고 성공 문구를 보여 줄 수 있었습니다. 이 슬라이스는 그 응답 계약을
화면에서 보수적으로 표면화합니다. 다만 현재 메일 상세 요청은
`action: "create"`와 기본값 `execute_provider: false`를 사용하므로 실제
CalDAV 공급자 412는 이 경로에서 아직 발생하지 않습니다. 따라서 이 PR은
공급자 실행을 새로 켜지 않으며, provider-backed writeback가 연결될 때
동일한 충돌 증거를 잃지 않도록 분류 계약을 고정합니다.

## Decision

응답에 존재하는 writeback-intent 증거 중에서 배치의 가장 강한 충돌 상태를
고릅니다.

1. `provider_status === 412`, `error_code` in `{etag_conflict,
   if_match_conflict, precondition_failed, schedule_conflict}`, 또는
   status에 `conflict`가 있으면 `conflict`.
2. `requires_if_match` 또는 `if_match`만 있으면 `warning`.
3. 그 외 `none`.

`conflict`는 오류 상태로 표면화하고 원본을 덮어쓰지 않았다고 말합니다.
충돌한 실행 항목 문구가 있으면 그 라벨을 그대로 인용합니다. 서버가
보낸 시각 창이 없으므로 시계 시각을 파싱·합성하지 않습니다.
동시에 메일 상세의 `일정 충돌 조율` 배지를 켜서 구매자가 목록과
같은 화면에서 확정 일정이 유지됐음을 보게 합니다.
`warning`은 If-Match 검사가 필요하다고 말합니다. 제품 이벤트
`calendar_reflected.conflict_state`는 이 분류를 그대로 실습니다.

HTTP 조건부 요청의 현재 표준 근거는 RFC 9110 §13, 특히 §13.1.1의
`If-Match`와 전제조건 실패 시의 412 의미입니다. RFC 7232는 RFC 9110에
의해 폐기되었으므로 현재 규범 근거로 사용하지 않습니다.

## Trust boundary

Naruon은 캘린더 호스트가 아닙니다. 충돌 판정은 고객 원본 계정의
CalDAV If-Match/ETag 증거에 의존합니다. 현재 메일 상세 경로는 intent-only라
실제 공급자 쓰기를 수행하지 않으며, 명시적 provider 실행 경로가 연결되기
전까지 412를 합성하거나 주장하지 않습니다. 서버가 시간 창을 아직 보내지
않으므로 이 슬라이스는 기존 writeback-intent 필드를 재사용하며, 허위
시간 파싱을 추가하지 않습니다.

## Verification contract

`frontend/src/lib/calendar-writeback-conflict.test.ts`는 금요일 15:00
확정 일정의 412 배치, 충돌 실행 항목 라벨 인용, If-Match-only 경고,
신규 슬롯 `none`을 고정합니다.
`EmailDetail.test.tsx`는 provider-backed 응답 모양의 412 증거가 메일 상세에
차단된 실행 항목 문구와 `일정 충돌 조율` 배지를 표시하고
`conflict_state: "conflict"`를 기록하는지 실행합니다. 실제 공급자 412의
end-to-end 검증은 명시적 `execute_provider` 경로와 고객 커넥터가 연결된
후속 작업으로 남기며, 이 PR의 intent-only 테스트를 실운영 증거로
표현하지 않습니다.

## Rollback

`EmailDetail`의 `conflict_state: "none"` 하드코딩과 기존 성공 문구로
되돌립니다. 헬퍼 모듈과 doctoring을 함께 제거합니다.

## References (APA 7th)

Daboo, C., Desruisseaux, B., & Dusseault, L. (2007). *Calendaring
extensions to WebDAV (CalDAV)* (RFC 4791). RFC Editor.
https://doi.org/10.17487/RFC4791

Fielding, R., Nottingham, M., & Reschke, J. (2022). *HTTP semantics*
(RFC 9110; STD 97). RFC Editor. https://doi.org/10.17487/RFC9110
