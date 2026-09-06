# HWP and HWPX attachment recognition implementation plan

## Goal

Implement the next #1350 evidence-pipeline slice by recognizing HWPX and HWP
attachments during deterministic email import without running heavy parsers or
model calls inline.

## Scope

- Extend the attachment parser manifest with HWPX and HWP parser families.
- Resolve generic binary MIME types from `.hwpx`, `.owpml`, and `.hwp`
  extensions.
- Retain exact source bytes as deferred base64 payloads after cheap family
  signature checks pass.
- Reject invalid HWPX/HWP payloads fail-closed before they enter worker queues.
- Keep `decode_deferred_attachment_payload()` backward-compatible for PDF while
  allowing explicit expected content types for HWPX and HWP workers.
- Add focused tests for manifest exposure, generic-MIME extension fallback,
  valid deferred payloads, invalid payload rejection, and decoder validation.
- Record the standards and product boundary in doctoring.

## Non-goals

This slice does not parse HWPX XML sections, reconstruct tables, extract embedded
images, run OCR, convert HWP binaries, or invoke LLM/VLM providers. Those remain
worker-backed follow-on tasks.

## Verification boundary

Hosted repository checks are authoritative. The local execution container could
not reach `github.com` DNS for checkout-based verification, so this branch does
not claim local test completion. Merge only after exact-head CI, security,
coverage, review, and protected-branch governance succeed.
