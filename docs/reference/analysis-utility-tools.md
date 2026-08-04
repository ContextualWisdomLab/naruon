# Analysis and security utility tools

Naruon exposes four deterministic utility tools for workflows that do not require a model call. Each tool validates its input and returns structured output suitable for later orchestration.

## `text_statistics_analyzer`

Calculates character, word, line, and sentence statistics from supplied text. Word boundaries follow Unicode whitespace rather than ASCII-only splitting, so multilingual input is handled consistently.

## `json_formatter`

Parses and formats JSON with deterministic key ordering. It rejects non-standard numeric values such as `NaN`, positive infinity, and negative infinity because those values are outside RFC 8259 JSON and cannot be transported reliably between conforming systems.

## `password_generator`

Uses Python's `secrets` module rather than a predictable pseudo-random generator. The caller selects the enabled character classes and requested length; a successful result contains at least one character from every enabled class. The tool rejects configurations that cannot satisfy that contract.

Generated passwords must be treated as sensitive output. They are not written to application logs or persisted automatically.

## `url_extractor`

Extracts HTTP and HTTPS URLs, including bracketed IPv6 hosts, while removing sentence-ending punctuation that is not part of the URL. The tool does not fetch, resolve, or otherwise contact the extracted destinations. Consumers must still apply the destination-policy and SSRF controls appropriate to the operation that eventually uses a URL.

## Integration boundary

These tools are standalone deterministic functions behind the normal tool registry. They do not require an LLM provider, network access, or database mutation. Naruon may compose them into larger workflows, but callers remain responsible for authorization, output handling, and any irreversible action that follows their results.
