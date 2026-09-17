# Calendar 첫 렌더 테스트 경고 수리

## 문제와 근거

기존 #1488의 `5a5789e04b9e8bcb50ddd22fbc411fc7581a24d8`에서 CalendarPage 테스트 10개는 통과했지만 첫 렌더 테스트가 CalendarLayout `act` 경고를 3번 출력했다. `CalendarLayout.tsx`의 원본 조회 effect는 응답을 받은 뒤 원본 목록, 선택한 원본, 준비 상태를 갱신한다. 첫 테스트가 동기 `act`로 렌더만 실행하고 비동기 응답을 기다리지 않아 이 갱신들이 경계 밖에서 일어났다.

원래 `console.error` 출력을 유지하는 spy와 테스트 정리 후 단언만 추가하자 1개 실패·9개 통과로 재현됐다. 경고를 무시하거나 테스트 수를 줄여 통과시킨 것이 아니다. 첫 테스트와 렌더를 비동기 `await act`로 바꿔 React가 예약한 갱신을 처리한 뒤 기존 화면 단언을 실행하도록 수리한다.

## 선택과 범위

이미 사용하는 React `act`를 재사용한다. 새 대기 라이브러리, 임의의 긴 타이머, API mock의 성공 응답 변경은 필요 없다. production effect의 요청, 취소·unmount 경계와 상태 갱신도 그대로 둔다. 진단 spy는 console을 복원한 뒤 경고를 단언하며 모든 CalendarPage 테스트와 정리 단계에 적용한다.

이 PR의 현재 direct parent는 #1245 `38c375e96693b69f5ce14c2a8bd50379f77e79e5`다. 2026-09-07 repair에서는 그 parent tree를 기준으로 Calendar 고유 delta만 다시 구성했다. 따라서 #1245가 소유하는 EmailDetail `act` 경고 수리, responsive action surface, dependency-security pin, CHANGELOG 및 다른 parent 계약은 이 PR에서 되돌리거나 복제하지 않는다. `AGENTS.md` 역시 별도 canonical documentation lane의 권위이므로 이 Calendar PR의 effective delta에서 제외한다.

현재 Calendar 고유 계약은 다음에 한정한다. 지원되지 않는 sidebar action은 노출하지 않고, 지원되는 `일정 수정 점검`만 기존 signed `/api/calendar/writeback-intent` update 경로에 연결한다. source registry가 준비되지 않았거나 writable source가 없으면 이 action은 disabled 상태를 유지한다. focused regression은 read-only source만 존재하는 ready registry에서 button disabled와 provider write 미호출을 고정한다.

## 검증 경계

과거 동일 Calendar product/test blob에서는 CalendarPage·writeback-readiness·SidebarRight의 13개 focused test와 관련 ESLint가 exit 0이었고 Calendar `act` 경고가 없었다. 이 결과는 과거 head의 development evidence다. 현재 parent 계약을 복원한 새 exact head에서는 GitHub-hosted checks와 독립 review를 새로 받아야 하며, 이전 head의 GREEN이나 review를 승계하지 않는다.

이 수리는 Calendar 테스트 스케줄링과 writeback-readiness 경계의 검증이다. 실제 공급자 쓰기 성공, 전체 WCAG 적합성, VoiceOver/NVDA/JAWS 발화, 전체 제품 100% coverage, p95 성능 또는 protected merge/release 완료를 의미하지 않는다.

재현 대상 명령은 `frontend`에서 다음과 같다.

```sh
corepack pnpm exec vitest run src/app/calendar/page.test.tsx src/components/CalendarLayout.writeback-readiness.test.tsx src/components/calendar/CalendarSidebarRight.test.tsx
corepack pnpm exec eslint src/app/calendar/page.test.tsx src/components/CalendarLayout.writeback-readiness.test.tsx src/components/calendar/CalendarSidebarRight.test.tsx src/components/CalendarLayout.tsx src/components/calendar/CalendarSidebarRight.tsx --max-warnings 0
```

## 참고 문헌

React. (n.d.). *act*. https://react.dev/reference/react/act
