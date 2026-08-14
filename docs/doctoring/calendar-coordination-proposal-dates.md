# Calendar coordination proposal dates

검토 기준일: **2026-08-14**

## Incident

회의 조율 1안/2안의 보이는 날짜와 `aria-label`이 `5월 23일 (목)`,
`5월 24일 (금)`으로 고정되어 있었습니다. 2026-05-23은 토요일이고
2026-05-24는 일요일입니다. 캘린더 헤더는 `2026년 5월`인데 요일만
틀리면 구매자가 제안 슬롯을 잘못된 요일로 조율합니다.

## Decision

제안 슬롯은 `calendarDisplayMonth`와 같은 `YYYY-MM` 월의 Seoul ISO
시각을 권위 데이터로 둡니다. 화면 문구와 `aria-label`은
`formatCoordinationProposalLabel`이 그 시각에서 월·일·요일·시각을
같이 만듭니다. 2026-05-21 14:00(+09) = 목, 2026-05-22 10:00(+09) = 금.

## Trust boundary

Naruon은 캘린더 호스트가 아닙니다. 이 슬라이스는 조율 UI의 날짜
표시만 고칩니다. CalDAV free-busy를 새로 만들지 않습니다.

## Verification contract

`frontend/src/components/calendar/helpers.test.ts`는 2026-05-23이
`(토)`로 나오고 1안이 `(목)`인지 고정합니다.
`CalendarCoordinationView.test.tsx`는 버튼 문구와 `aria-label`이
같은 포맷터 결과를 쓰는지 실행합니다.

## Rollback

하드코드된 `5월 23일 (목)` / `5월 24일 (금)` 문구로 되돌립니다.

## References (APA 7th)

Daboo, C., Desruisseaux, B., & Dusseault, L. (2007). *Calendaring
extensions to WebDAV (CalDAV)* (RFC 4791). RFC Editor.
https://doi.org/10.17487/RFC4791

International Organization for Standardization. (2019). *Date and
time — Representations for information interchange — Part 1: Basic
rules* (ISO 8601-1:2019).
