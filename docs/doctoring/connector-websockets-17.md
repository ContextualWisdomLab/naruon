# Connector WebSockets 17 dependency boundary

## Decision

The standalone connector and the Naruon-integrated connector use the same exact
`websockets==17.0.1` dependency and hash-locked artifact set. The lock records
the source distribution and the CPython 3.14 manylinux x86_64 wheel required by
the supported CI and deployment path. Application behavior, credentials, API
contracts, database objects, and reviewer identities are unchanged.

The major-version update remains acceptable only while connector compilation,
hash-locked installation, and the real request-header compatibility path pass on
the exact pull-request head. No predecessor-head or Dependabot-owned branch
evidence is reused for this maintainer-owned replacement.

## Verification contract

- `pip install --require-hashes` resolves only the reviewed artifacts.
- The installed package reports version `17.0.1`.
- The connector's asynchronous client path uses the supported
  `additional_headers` interface where custom request headers are required.
- Repository CI, security, dependency review, static analysis, and container
  checks pass on the exact head.
- The connector continues to operate independently and when imported as a Naruon
  module.

## Rollback

Rollback restores the `16.1` requirement and its prior artifact hash in both
connector requirement files. Rollback does not alter connector credentials,
network destinations, or reviewer automation.

## References

Python Packaging Authority. (2026). *Secure installs*. pip documentation.
https://pip.pypa.io/en/stable/topics/secure-installs/

WebSockets project. (2026). *Changelog*. websockets documentation.
https://websockets.readthedocs.io/en/stable/project/changelog.html
