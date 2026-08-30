# DAV Production Capability Contract

Naruon exposes only DAV operations that have complete tenant authorization,
persisted data, deterministic tests, and production handlers.

## Supported DAV methods

| Method | Status | Production behavior |
| --- | --- | --- |
| `OPTIONS` | Supported | Returns `DAV: 1` and advertises only `OPTIONS, PROPFIND`. |
| `PROPFIND` | Supported | Returns tenant-scoped project collections from PostgreSQL. |

The router does not register `GET`, `PUT`, `DELETE`, `MKCOL`, `REPORT`,
`PROPPATCH`, `COPY`, `MOVE`, `LOCK`, or `UNLOCK`. FastAPI therefore returns
`405 Method Not Allowed` rather than exposing success-shaped or `501` stubs.
Mutation is available only through Naruon's authenticated writeback-intent
workflow until each DAV verb has provider capability discovery, precondition
handling (`ETag`/`If-Match` where applicable), durable audit evidence, and real
connector execution.

## Data and identity boundary

- DAV paths must contain the authenticated owner user ID.
- Project folders come from the persisted `project_folder` registry and are
  scoped by user and organization.
- Connected WebDAV accounts come from `webdav_account` records; hard-coded demo
  accounts and folders are forbidden.
- Runtime code must not return successful attachment synchronization when no
  provider write occurred.
- XML values are escaped and request-path control characters are encoded before
  logging.

## Verification

Every changed DAV capability requires:

1. a fail-first API regression;
2. tenant and owner authorization tests;
3. positive provider or database integration evidence;
4. negative tests for unsupported methods and stale preconditions;
5. production statement and branch coverage of 100%; and
6. exact-head security and required checks before merge.

## Primary standard — APA 7th

Dusseault, L. (2007). *HTTP extensions for Web Distributed Authoring and
Versioning (WebDAV)* (RFC 4918). Internet Engineering Task Force.
https://doi.org/10.17487/RFC4918
