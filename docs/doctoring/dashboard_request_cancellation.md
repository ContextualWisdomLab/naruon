# Dashboard request cancellation

## Evidence and decision

PR #1570 at `a48e8ba85b6d3a4ceb78e110582b3d5bc76d0d7c` protected state
updates with a cancelled flag and request generation, but its five dashboard
GET requests shared only a 15-second timeout signal. Retrying or leaving the
dashboard made responses irrelevant without aborting those fetches. The same
file's startup-search effect already aborts its controller during cleanup.

Reuse that native pattern for the dashboard generation. Combine its controller
with the existing timeout signal using `AbortSignal.any`, then mark the
generation cancelled before aborting in cleanup. This preserves the five API
routes, signed-cookie transport, independent source states and request-version
guard. It does not change model timeouts or claim that abort rolls back work
already accepted by a server. These are read requests, not provider writes.

Do not replace the timeout, increase its duration, add a client wrapper, or
depend on ignoring stale responses alone. A retry gets a fresh controller;
cleanup must never abort that newer generation.

## Verification and limits

The existing retry-race harness now inspects all five old signals and all five
new signals, still delivers a late old response, and checks final unmount.
A StrictMode case checks discarded-mount cancellation, active-mount survival,
absence of a spurious error alert, and final cleanup. Both tests failed before
the source repair. Afterward, those cases plus dashboard, succession (including
the existing 15,000 ms timeout test), and API-client contracts passed: 30 tests.
Mock signal assertions prove cancellation delivery, not server-side cleanup or
measured bandwidth savings. Hosted checks and protected merge remain separate.

Focused lint with zero allowed warnings and TypeScript checking passed.
Native signal smoke checks passed in installed Chromium 151.0.7922.34,
Firefox 153.0 and WebKit 26.5 for both manual abort and timeout reason.
The full suite passed 53 files / 448 tests, but retained three CalendarLayout
and four EmailDetail act diagnostics outside this repair. Their existing owner
repairs must be inherited and revalidated; this is not warning-free full-suite
evidence or permission to suppress those diagnostics.

MDN lists `AbortSignal.any` as Baseline 2024; older browsers need an explicit
support decision before adoption. Do not claim a repository-wide browser
support policy from the local engine smoke checks or add a speculative polyfill.

## Reference

MDN contributors. (2026, September 1). *AbortSignal: any() static method*.
MDN Web Docs. https://developer.mozilla.org/en-US/docs/Web/API/AbortSignal/any_static
