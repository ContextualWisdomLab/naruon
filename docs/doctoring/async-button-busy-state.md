# Async button busy-state accessibility

## Decision

Naruon exposes `aria-busy=true` only while an action control is actively processing its asynchronous operation. The existing `disabled` behavior remains responsible for preventing duplicate activation; `aria-busy` communicates the processing state to the accessibility API rather than replacing the disabled-state contract.

The bounded change applies to the project evidence-review action, repository document actions, and duplicate-thread intent action. It does not claim whole-product accessibility conformance or imply that every statically disabled control is busy.

## Evidence boundary

WAI-ARIA defines `aria-busy` as a state indicating that an element is being modified and that assistive technologies can defer exposing intermediate changes until the operation is complete. The attribute is defined for all elements in the base markup and defaults to `false`. This supports binding `aria-busy` to the same boolean state that represents the in-flight asynchronous action, while leaving ordinary unavailable controls unmarked as busy.

## Verification

Merge readiness is determined only from the unchanged current PR head after repository CI, security, coverage, review, and protected-branch requirements pass. The accessibility attribute itself is not a substitute for rendered assistive-technology testing across supported environments.

## Reference — APA 7th

World Wide Web Consortium. (2026, June 4). *Accessible Rich Internet Applications (WAI-ARIA) 1.3* (Working Draft). https://www.w3.org/TR/2026/WD-wai-aria-1.3-20260604/
