# Calendar 첫 렌더 테스트 경고 수리

## 문제와 근거

기존 #1488의 `5a5789e04b9e8bcb50ddd22fbc411fc7581a24d8`에서 CalendarPage
테스트 10개는 통과했지만 첫 렌더 테스트가 CalendarLayout `act` 경고를
3번 출력했다. `CalendarLayout.tsx`의 원본 조회 effect는 응답을 받은 뒤
원본 목록, 선택한 원본, 준비 상태를 갱신한다. 첫 테스트가 동기 `act`로
렌더만 실행하고 비동기 응답을 기다리지 않아 이 갱신들이 경계 밖에서 일어났다.

원래 `console.error` 출력을 유지하는 spy와 테스트 정리 후 단언만 추가하자
1개 실패·9개 통과로 재현됐다. 경고를 무시하거나 테스트 수를 줄여 통과시킨
것이 아니다. 첫 테스트와 렌더를 비동기 `await act`로 바꿔 React가 예약한
갱신을 처리한 뒤 기존 화면 단언을 실행하도록 수리한다.

## 선택과 범위

이미 사용하는 React `act`를 재사용한다. 새 대기 라이브러리, 임의의 긴
타이머, API mock의 성공 응답 변경은 필요 없다. production effect의 요청,
취소·unmount 경계와 상태 갱신도 그대로 둔다. 진단 spy는 console을 복원한
뒤 경고를 단언하며, 모든 CalendarPage 테스트와 정리 단계에 적용한다.

이 수리는 Calendar 테스트 스케줄링의 검증이다. 실제 화면의 Visual
Inspection, 접근성 전 범주, 공급자 쓰기, 전체 제품 커버리지 또는 보호
병합을 완료했다는 뜻은 아니다. 별도 EmailDetail 경고 수리는 기존 #1245에
있으며 이 PR에서 복제하지 않는다.

## 실행 명령

수리 후 CalendarPage·writeback-readiness·SidebarRight의 13개 테스트와
관련 파일의 `eslint --max-warnings 0` 검사가 exit 0이며 Calendar `act`
경고는 없다. 전체 실행은 53파일·440테스트가 통과했지만 이 브랜치에 아직
상속되지 않은 EmailDetail 경고 4개가 남는다. #1245의 수리를 상속한 뒤
다시 검증해야 하며, 이번 결과를 전체 경고 제거로 표시하지 않는다.

`frontend`에서 실행한다.

```sh
corepack pnpm exec vitest run src/app/calendar/page.test.tsx src/components/CalendarLayout.writeback-readiness.test.tsx src/components/calendar/CalendarSidebarRight.test.tsx
corepack pnpm exec eslint src/app/calendar/page.test.tsx --max-warnings 0
```

## 참고 문헌

React. (n.d.). *act*. https://react.dev/reference/react/act
