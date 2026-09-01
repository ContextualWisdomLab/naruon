# Self-hosted connector registration naming boundary

The self-hosted connector schema is an organization-owned bounded context. Its Python model vocabulary therefore uses semantically specific multiword names while preserving the established HTTP/JSON wire contract at the adapter boundary.

## Repair

- `SelfHostedConnectorRegistrationRequest.capabilities` → `connector_capabilities`
- `SelfHostedConnectorRegistrationResponse.status` → `registration_status`

The legacy JSON keys `capabilities` and `status` remain accepted and emitted as Pydantic aliases. `populate_by_name=True` also permits organization-owned callers to use the semantic field names directly. This isolates generic compatibility names at serialization/deserialization instead of treating them as authoritative internal vocabulary.

## Compatibility and persistence

No database table, persisted record, migration, foreign key, index, UPSERT path, or lock boundary is changed. Code search on the protected `develop` head found these schema classes defined only in `backend/schema/connector.py`, so there are no repository-local callers to migrate. Regression coverage asserts both the semantic model-field names and the unchanged legacy wire aliases.
