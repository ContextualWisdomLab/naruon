# ADR-0004: Fail-closed input safety and evidence-first judgment

- Status: Accepted
- Date: 2026-08-11

## Context

The live Compose smoke exposed a PostgreSQL failure caused by a NUL byte in a
`text` advisory-lock parameter. Signed session claims also accepted ASCII NUL
characters because ASCII validation alone is insufficient. Separately, the
project-graph configuration described keyword extraction as fallback/reference
only while selecting it as the default.

## Decision

- Reject NUL and other control characters at authentication, local HTTP, and
  other trust boundaries; add a regression test whenever a boundary is changed.
- Never pass a raw NUL-delimited composite value to a PostgreSQL text parameter.
  Derive lock keys from a deterministic NUL-free digest and reject NUL-bearing
  owner identities before persistence or locking.
- Keyword matching is not a base judgment. Grounded LLM or
  contextual-orchestrator extraction is the default; deterministic keyword
  extraction is explicit reference/diagnostic evidence and a last-resort
  fallback with provenance, not an authoritative decision.
- Any suspicious behavior is an actionable defect: trace its shared root cause,
  make the smallest safe correction, and rerun the focused and live checks. A
  pending external operation is a wait state, not permission to bypass safety
  or to stop investigating.
- Live smoke tooling must receive session secrets through the environment and
  must never print bearer tokens or console snippets that reproduce them.

## Consequences

- Malformed identities and unsafe text fail closed before reaching PostgreSQL or
  external requests.
- Local reference extraction remains available for diagnostics, while default
  semantic judgments require grounded evidence.
- The test and live-smoke loop becomes part of the correction contract rather
  than an optional postscript.

## References

- Jerome H. Saltzer and Michael D. Schroeder, [“The Protection of Information
  in Computer Systems”](https://www.cs.virginia.edu/~evans/cs551/saltzer/),
  *Proceedings of the IEEE* 63(9) (1975). The paper's fail-safe defaults,
  complete mediation, least privilege, and separation-of-privilege principles
  support rejecting malformed input before persistence or authorization.
- Lianmin Zheng et al., [“Judging LLM-as-a-Judge with MT-Bench and Chatbot
  Arena”](https://arxiv.org/abs/2306.05685), NeurIPS 2023. The paper documents
  useful agreement with human preferences together with position, verbosity,
  self-enhancement, and reasoning biases; this supports grounded evidence and
  explicit provenance rather than keyword matching as an authoritative
  judgment.

The source PDFs are not bundled because redistribution rights were not
established; stable links and summaries are provided instead.
