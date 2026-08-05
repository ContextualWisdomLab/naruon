# EmailDetail responsive action surface doctoring

## Decision

The email detail view exposes participants and attachment names at every viewport
size. Attachments use a horizontally scrollable, explicitly named region so a
small viewport does not silently remove source evidence. The meeting-conflict
panel reuses the existing calendar writeback-intent handler rather than rendering
an inert call-to-action. Loading, disabled, and polite live-status states remain
in the same product surface.

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
- The meeting action is disabled when no extracted action item exists.
- Activating the meeting action sends the exact writeback-intent request.
- Successful writeback intent produces a polite live status.
- The three unrelated backend files are byte-identical to the exact PR base.
- Frontend focused tests, full tests, lint, type checking, coverage collection,
  and production build run before the verified commit is published.

## Exact repair evidence

The bounded repair run on August 5, 2026 completed the focused EmailDetail suite
with 24 passing tests and the complete frontend suite with 428 passing tests
across 49 files. Type checking, ESLint, V8 coverage collection, and the Next.js
production build also completed successfully. Before publication, the workflow
compared all three excluded backend files with their exact Git blobs at PR base
`be3bedb4bc5f264c9d621e2666b8583b3b149eca` and removed its temporary workflow
and repair script. Repository-required checks on the final maintainer-owned head
remain authoritative for merge eligibility.

The run emitted pre-existing React `act(...)` diagnostics from older tests. They
did not fail the suite, but this record does not characterize the overall test
suite as warning-free.

## References

World Wide Web Consortium. (2023). *Web Content Accessibility Guidelines
(WCAG) 2.2*. https://www.w3.org/TR/WCAG22/

World Wide Web Consortium. (n.d.). *Understanding success criterion 2.4.7:
Focus visible*. Retrieved August 5, 2026, from
https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html

World Wide Web Consortium. (n.d.). *Understanding success criterion 4.1.3:
Status messages*. Retrieved August 5, 2026, from
https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html
