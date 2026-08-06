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

## References

World Wide Web Consortium. (2023). *Web Content Accessibility Guidelines
(WCAG) 2.2*. https://www.w3.org/TR/WCAG22/

World Wide Web Consortium. (n.d.). *Understanding success criterion 2.4.7:
Focus visible*. Retrieved August 5, 2026, from
https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html

World Wide Web Consortium. (n.d.). *Understanding success criterion 4.1.3:
Status messages*. Retrieved August 5, 2026, from
https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html
