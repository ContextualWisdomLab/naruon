# Async button busy-state accessibility

## Decision

Naruon exposes `aria-busy=true` only while the action represented by that control is actively processing. The existing `disabled` behavior remains responsible for preventing conflicting or duplicate activation; `aria-busy` communicates the processing state to the accessibility API rather than replacing the disabled-state contract.

The bounded change applies to project candidate confirmation, project evidence-review save, repository document actions, and duplicate-thread intent actions. It does not claim whole-product accessibility conformance or imply that every statically disabled control is busy.

## Evidence boundary

WAI-ARIA defines `aria-busy` as a state indicating that an element is being modified and that assistive technologies can defer exposing intermediate changes until the operation is complete. The attribute is defined for all elements in the base markup and defaults to `false`. This supports binding `aria-busy` to the state of the represented asynchronous action while leaving controls disabled for another reason non-busy.

A read-only prerequisite is therefore distinct from the mutation it gates. The project evidence-review button remains disabled while full evidence is being fetched, but that evidence GET does not make the correction-save button busy. `aria-busy` becomes true only after the user starts the correction save.

## Action identity and lifecycle

Repository document actions share a mutual-exclusion lock because concurrent upload, reparse, embedding regeneration, HWP conversion, and WebDAV materialization can race over the same refreshed quality surface. That shared lock is separate from action identity: only the initiating control exposes `aria-busy=true`; disabled siblings remain `aria-busy=false`.

The lock covers the complete action lifecycle, including the quality-surface refresh that follows a successful document mutation. A mutation is not reported as complete and the shared lock is not released while that refresh is still pending. The in-memory guard prevents programmatic re-entry as well as duplicate pointer or keyboard activation, and cleanup clears an active identity only when it still belongs to the completing operation.

## Regression evidence

- `frontend/src/components/data-layout/DocumentRepositoryTab.busy-state.test.tsx` verifies the rendered document-action group reports only the initiating action as busy.
- `frontend/src/components/DataLayout.document-action-lifecycle.test.tsx` holds the post-action quality refresh pending and verifies a second document action cannot start before the first lifecycle settles.
- `frontend/src/components/ProjectsLayout.accessibility.test.tsx` verifies candidate-confirmation busy state and verifies a pending evidence GET disables the evidence-review save without announcing that save as busy.

These regressions are source-level evidence. Merge readiness is determined only from the unchanged exact PR head after repository CI, security, coverage, review, and protected-branch requirements pass. The attributes and automated DOM tests are not a substitute for rendered assistive-technology validation across supported environments.

## Reference — APA 7th

World Wide Web Consortium. (2026, June 4). *Accessible Rich Internet Applications (WAI-ARIA) 1.3* (Working Draft). https://www.w3.org/TR/2026/WD-wai-aria-1.3-20260604/
