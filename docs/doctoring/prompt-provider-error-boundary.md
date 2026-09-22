# Prompt provider error logging boundary

## Observed failure

PR #1563 originally replaced exception interpolation with `exc_info=True`.
Python traceback formatting still includes the exception message, so a provider
exception containing an authorization header, credential, internal URI, or
customer prompt could still cross the application log boundary.

## Current contract

`execute_prompt_with_llm` records a fixed operation name and the exception class
only. It does not record the exception message or traceback, while the signed API
returns a fixed actionable 502 response. The regression raises a provider error
containing a sentinel bearer value and proves that neither the value nor header
label appears in captured logs. This keeps enough event classification for
operations without copying provider-controlled detail into a broader log trust
domain.

Client cleanup follows the same boundary. If both the provider operation and
client close fail, cleanup records only a fixed event and exception class; it
cannot replace the fixed 502 response or expose either exception message.

OWASP recommends removing, masking, sanitizing, hashing, or encrypting access
tokens, credentials, connection strings, and other sensitive values before log
recording. NIST SP 800-92 frames log management as an enterprise lifecycle that
must account for the confidentiality and protection of collected records. These
sources support the narrow fixed-event/type record; they do not establish that
all tracebacks are safe or that exception text is non-sensitive.

No PDF is committed: the OWASP source is maintained as an online cheat sheet,
and this change cites the official NIST publication and DOI rather than copying
an externally hosted binary whose redistribution status was not independently
verified in this PR.

## Verification

- protected base: `develop@042b0c70531b229af3acbd0421a2f23098d848b3`
- reviewed implementation head before this doctoring commit:
  `164d1e85700001978cee0cb131ba33fe8e3c1498`
- prerequisite: PR #1565
  `3a4ec5833db649994dc0042653d1d29f71010cfd`
- verified implementation stack before this doctoring update:
  `58eabe7bc75d413e9d784b60b049264cdb5157b2`
- `PYTHONWARNINGS=error … pytest -q` across prompt, dependency-pin, and release
  governance contracts: 58 passed
- Ruff on the prompt route and regression file: passed
- protected-base diff check: passed

Hosted checks and reviews must be regenerated for the resulting exact head.

## References

Kent, K., & Souppaya, M. (2006). *Guide to computer security log management*
(NIST Special Publication 800-92). National Institute of Standards and
Technology. https://doi.org/10.6028/NIST.SP.800-92

OWASP Foundation. (n.d.). *Logging cheat sheet*. OWASP Cheat Sheet Series.
Retrieved September 5, 2026, from
https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
