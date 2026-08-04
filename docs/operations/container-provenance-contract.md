# Container provenance contract

Naruon container images must be reproducible from reviewable, immutable base-image inputs.

## Required invariants

- Every production `FROM` instruction uses both a human-readable image tag and a full `sha256` digest.
- The root, backend, connector, and frontend Dockerfiles keep shared Python and Node base references synchronized where the runtime contract is shared.
- OCI `org.opencontainers.image.base.name` and `org.opencontainers.image.base.digest` annotations are derived from the actual first Dockerfile stage rather than duplicated constants.
- Published multi-platform images preserve annotations at both the manifest and index levels.
- Pull-request validation resolves the pinned Ollama manifest and fails closed when either `linux/amd64` or `linux/arm64` is absent.
- Dependency and image security pins remain governed by repository tests; a dependency upgrade must update its hash-locked artifact and the corresponding regression contract together.

## Change procedure

1. Update the tag-and-digest reference in the canonical Dockerfile.
2. Synchronize every Dockerfile that shares that runtime.
3. Regenerate affected hash locks without weakening `--require-hashes` installation.
4. Update `CHANGELOG.md` when the runtime or published artifact changes.
5. Run release-governance, repository-hygiene, application, image-build, and security checks on the exact pull-request head.
6. Merge only after independent review confirms that the OCI annotations describe the image that is actually built.

A mutable tag by itself, a digest without its reviewable tag, or an annotation that does not match the first stage violates this contract.
