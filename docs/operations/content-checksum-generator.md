# Content checksum generator

**Availability:** this capability is not shipped until its implementation passes protected-`develop` integration and review gates.

Use `content_checksum_generator` when a customer needs to determine whether two pieces of text have the same exact UTF-8 byte representation. It is appropriate for export verification, evidence comparison, and reproducible workflow receipts. It is not sender authentication and it does not replace a MAC or digital signature.

## Decide which algorithm to use

- Choose `sha256` for the broadest SHA-2 interoperability.
- Choose `sha3_256` when the receiving workflow explicitly uses SHA3-256.
- Choose `blake2b_256` when both sides agree on BLAKE2b with a 256-bit digest.

Do not substitute MD5, SHA-1, aliases, or differently sized BLAKE2 outputs; the tool rejects them rather than guessing what the caller intended.

## Execute

Call the existing authenticated tool endpoint with the tool code and the two required parameters:

```json
{
  "text": "content to compare",
  "algorithm": "sha256"
}
```

The tool reports `algorithm_code`, `digest_hex`, `byte_length`, `encoding_code`, and `security_note`. Input is limited to 1,048,576 bytes **after** UTF-8 encoding. Canonically equivalent Unicode text can produce different digests when its byte sequences differ because Naruon does not normalize the source before hashing.

## Take the next action

1. Obtain the expected digest through an independent trusted channel or from the system that produced the reference artifact.
2. Confirm the algorithm identifiers are identical on both sides.
3. Compare the complete hexadecimal digests exactly.
4. If they differ, treat the contents as non-identical and investigate source encoding/content provenance; do not truncate or approximately compare the digest.
5. If the business decision depends on who created or authorized the content, use the relevant authenticated provenance/signature workflow instead of interpreting checksum equality as identity proof.

## Failure handling

An unsupported algorithm or oversized payload fails closed with a deterministic validation error. Operators should change the requested algorithm to an allowlisted value or split/restructure the calling workflow; they should not bypass the limit or add a legacy digest solely to make a failed request pass.

Architecture decision: [`ADR-0004`](../adr/0004-bounded-content-checksum-surface.md). Standards and APA 7 references: [`docs/doctoring/content-checksum-generator.md`](../doctoring/content-checksum-generator.md).
