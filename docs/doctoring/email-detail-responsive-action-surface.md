# EmailDetail responsive action surface doctoring

## Decision

The email detail view exposes participants and attachment names at every viewport
size. Attachments use a horizontally scrollable, explicitly named region so a
small viewport does not silently remove source evidence. The meeting-conflict
panel reuses the existing calendar writeback-intent handler rather than rendering
an inert call-to-action. The user must select an opaque source returned by the
signed server registry before the action is enabled; every intent carries that
exact `target_source_id`, and a source conflict clears the selection so the user
must confirm the current source again. Mixed batch outcomes preserve successful
intents, report the failed count, and never relabel a source identifier as a
provider calendar-event identifier. Loading, disabled, and polite live-status
states remain in the same product surface.

Calendar-source state is keyed to the active email and actionable summary
context. A navigation or summary-context change therefore derives an empty,
non-confirmed loading or idle view immediately instead of reusing a source from a
previous email. Registry success or failure publishes state only from the still
mounted request for that exact context; stale requests cannot reactivate an old
selection. This fail-closed lifecycle also avoids synchronous state resets inside
the React effect while preserving explicit confirmation.

Unrelated backend changes are excluded from this UI slice. Thread identifier,
SMTP destination, import-format, and tenant-scope policy changes require their
own security rationale and regression contracts rather than hitchhiking on a
presentation PR.

## Accessibility boundary

The implementation preserves native button semantics and the repository's
keyboard-visible focus system, gives the attachment evidence region an
accessible name, and exposes asynchronous status through `role=status` and
`aria-live=polite`. WCAG 2.2 is used as the current normative target. The focused
regression proves discoverability and activation in the DOM, but this record does
not claim full WCAG conformance without contrast, zoom, assistive-technology, and
manual usability evidence.

## Verification contract

- The participant list renders without an unsafe type assertion.
- The attachment rail is present and not hidden on small viewports.
- The meeting action is disabled when no extracted action item exists, while the
  request is pending, or until one current server-authorized source is confirmed.
- Activating the meeting action sends the exact opaque `target_source_id` with
  every writeback-intent request.
- A `409` source conflict clears confirmation and requires explicit reselection.
- Source state is never reused across email or actionable-summary context keys,
  and an unmounted registry request cannot publish stale state.
- Complete and partial batches produce distinct polite status evidence, and
  analytics never treat `target_source_id` as a provider event identifier.
- The three unrelated backend files are byte-identical to the exact PR base.
- Frontend focused tests, full tests, lint, type checking, coverage collection,
  and production build run before the verified commit is published.

## 입력 이벤트와 Hook 의존성 경고 수리

PR #1245의 `796b34c5a1322f09c6f00b8cf24591ae04b89b6b`에서 EmailDetail
테스트 26개는 React `act` 경고 4개를 출력하고도 exit 0으로 끝났다.
초안 지시 입력, 초안 지우기, 전송 성공·실패 테스트가 native value setter와
입력 이벤트를 `act` 밖에서 실행했고, 이후 버튼 클릭만 감쌌다. 입력 자체가
React 상태 갱신을 예약하므로 나중의 클릭을 감싸는 것으로는 해결되지 않는다.
이전 커밋의 재현 근거는 다음 기록에 남아 있다.
https://github.com/ContextualWisdomLab/naruon/pull/1244#issuecomment-5559885208

원래 출력을 유지하는 `console.error` spy로 각 테스트의 정리 단계까지
`not wrapped in act` 발생 여부를 검사하고, 단언 전에 console을 복원한다.
검사만 추가했을 때 4개 실패·22개 통과로 재현됐다. 기존 setter/event 쌍
4개를 `await act(async () => ...)`로 감싼 뒤에는 EmailDetail과
calendar-writeback 테스트 30개가 해당 경고 없이 통과했다. 실패 경로의
API 오류 로그는 그대로 출력하며, 경고를 숨겨 통과시키지 않는다.

이후 lint에서 같은 컴포넌트의 `setSelectedWritebackSourceId` 의존성 누락을
발견했다. 일반 lint는 경고 1개와 exit 0을 반환했지만 `--max-warnings 0`은
exit 1로 실패했다. 이 함수는 안정적인 React state setter가 아니라
`sourceContextKey`와 `sourceContextIsActionable`에 따라 바뀌는 콜백이다.
일정 반영 콜백이 현재 선택 문맥을 사용하도록 의존성 목록에 추가한다.
공급자 호출 계약이나 CalendarPage 테스트는 바꾸지 않는다.

이미 사용하는 React 도구로 해결하므로 새 상호작용 라이브러리나 공통
래퍼는 추가하지 않는다. 이 수리는 실제 브라우저 동작, 전체 테스트의 모든
경고 제거, 최신 Visual Inspection 또는 보호 병합 완료를 뜻하지 않는다.
Context7은 사용량 한도로 조회에 실패해 아래 React 공식 문서의 비동기
이벤트 처리 지침을 확인했다.

`frontend`에서 실행할 검증 명령:

```sh
corepack pnpm exec vitest run src/components/EmailDetail.test.tsx src/components/EmailDetail.calendar-writeback.test.tsx
corepack pnpm exec eslint src/components/EmailDetail.tsx src/components/EmailDetail.test.tsx --max-warnings 0
```

수리 후 위 테스트 30개와 전체 `eslint . --max-warnings 0`, 타입 검사,
프로덕션 빌드는 exit 0이다. 전체 커버리지 실행은 52파일·442테스트가
통과했지만 별도 CalendarLayout `act` 경고 3개는 남았다. 커버리지는
lines 86.76%, statements 84.06%, functions 85.67%, branches 75.18%로
100% 목표를 충족하지 못한다. 측정 대상을 줄이거나 남은 경고를 숨기지
않으며, 이 결과를 전체 제품의 검증 완료로 표시하지 않는다.

## References

React. (n.d.). *act*. https://react.dev/reference/react/act

World Wide Web Consortium. (2023). *Web Content Accessibility Guidelines
(WCAG) 2.2*. https://www.w3.org/TR/WCAG22/

World Wide Web Consortium. (n.d.). *Understanding success criterion 2.4.7:
Focus visible*. Retrieved August 5, 2026, from
https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html

World Wide Web Consortium. (n.d.). *Understanding success criterion 4.1.3:
Status messages*. Retrieved August 5, 2026, from
https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html
