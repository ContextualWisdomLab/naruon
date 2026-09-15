# Exception telemetry confidentiality boundary

## Authority and scope

Issue #1698 owns the repository-wide logging-confidentiality gap. This change is a stacked successor to #1612 (`3da3ae8e60e1bb049f59ae86bfe82db12b7e3cc7`), which already removed raw exception values from its bounded exception-redaction surface. It does not rewrite unrelated log sites or claim #1698 complete.

The predecessor helper replaced the exception value but retained the original traceback. That prevents the original exception message from being rendered, but traceback formatting still exposes source locations and creates a larger operational disclosure surface than normal production logs require. The successor keeps the existing caller contract while replacing traceback output with bounded correlation evidence.

## Decision

`core.safe_logging.redacted_exception_info()` remains the compatibility boundary for #1612 consumers. It now returns logging exception information with:

- a fixed redaction marker;
- the exception class name;
- a 16-hex SHA-256 correlation fingerprint derived from the exception's qualified type and deepest traceback module/function identity;
- no original exception value;
- no original traceback object.

The original traceback is inspected in memory only to build the one-way fingerprint. File paths, source lines, locals, exception messages, causes, contexts, provider responses, credentials, tokens, and connection strings are not formatted into the emitted record. The caller's fixed log message remains the operation code/context, so RCA can group failures by operation, exception class, and fingerprint without recording secret-bearing exception text.

## Alternatives rejected

`exc_info=True` is rejected as a confidentiality mechanism because Python logging renders the exception value and traceback. Replacing only the exception value while preserving the original traceback is safer than raw logging but still exposes source locations and is not the default production contract. Suppressing exception diagnostics entirely is also rejected because it removes correlation needed for incident response.

## Verification

`backend/tests/test_safe_logging.py` exercises the real `logging.Formatter` path with token-like text, a database connection string, and two distinct secret-bearing messages from the same failure site. The contract requires that the rendered record contains neither the secret text nor the test source path/function name, while retaining the exception class and a stable message-independent fingerprint. A no-traceback exception is covered separately.

This PR does not resolve every sink named by #1698. Protected `develop` still contains other `exc_info=True` and raw exception-interpolation sites outside #1612's bounded surface. Those require sink-by-sink data-flow review and ordinary successor work; blanket string replacement is explicitly out of scope.

## Traceability

- CWE-532 maps the risk to sensitive information written to logs and specifically notes that full path names and system information can create an additional disclosure path.
- The OWASP Logging Cheat Sheet advises excluding or sanitizing access tokens, sensitive personal data, passwords, database connection strings, encryption keys, and other primary secrets from ordinary logs.

### References

MITRE. (2026). *CWE-532: Insertion of sensitive information into log file* (CWE Version 4.20). https://cwe.mitre.org/data/definitions/532.html

OWASP Foundation. (n.d.). *Logging cheat sheet*. OWASP Cheat Sheet Series. Retrieved September 16, 2026, from https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
