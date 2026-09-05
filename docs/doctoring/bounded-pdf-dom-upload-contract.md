# Doctoring record: bounded PDF DOM upload contract

**Observed gap:** The signed Data workspace PDF upload rejected files above
20MiB while Naruon's planned shared admission bound is 64MiB. The current
NewsDOM immutable release and an exact Naruon pin proving 64MiB support have
not been verified; this record must not present that proposal as provider runtime.

**Proposed correction:** After NewsDOM publishes an immutable 64MiB release and
Naruon pins it exactly, the upload endpoint and pending-payload decoder will
share a 64MiB bound. Signature validation, signed-session authorization, base64
storage, worker deferral, and `413` rejection remain fail-closed. The Naruon PR
stays Draft until that owner evidence exists.

**Evidence:** `backend/tests/test_data_api.py` asserts the 64MiB contract and
keeps the over-limit test monkeypatched to a small fixture. The NewsDOM sidecar
alignment is tracked separately in its own ADR and PR.
The four existing focused PDF tests use mocks and reduced over-limit fixtures;
they do not prove a real 64MiB PDF processed by a released NewsDOM service.
[ADR-0021](../adr/0021-bounded-pdf-dom-upload-contract.md) preserves the
proposal formerly numbered 0005, whose number collided with unrelated PRs.

**References (APA 7th):**

- Internet Engineering Task Force. (2022). *HTTP semantics (RFC 9110).* RFC
  Editor. https://www.rfc-editor.org/rfc/rfc9110
- National Institute of Standards and Technology. (2025). *Secure software
  development framework (SSDF) version 1.2* (NIST SP 800-218 Rev. 1, Initial
  Public Draft). https://doi.org/10.6028/NIST.SP.800-218r1.ipd

No customer or private reference data was read, and no source PDF is
redistributed.
