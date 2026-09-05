# Ticket-task semantic identifiers

## Decision

Naruon's Tasks bounded context owns ticket-task identity, title, lifecycle state, priority, and reply-SLA escalation results. Organization-owned Python model fields now carry that meaning explicitly instead of relying on generic one-word names.

The authoritative internal names are `task_uid`, `task_title`, `task_status`, `task_priority`, `task_items`, `created_task_count`, `ticket_tasks`, `escalation_limit`, `evaluated_email_count`, and `reply_sla_policy`. The reply-SLA service result uses `ticket_task`, `evaluated_email_count`, `created_task_count`, and `ticket_tasks` for the same ubiquitous language.

## Compatibility boundary

The existing `/api/tasks` JSON contract is preserved. Pydantic aliases translate the semantic internal fields to the established external keys `id`, `title`, `status`, `priority`, `items`, `created`, `tasks`, `limit`, `evaluated`, and `policy`. Existing clients therefore do not need an immediate wire migration, while new organization-owned code no longer uses those generic keys as its internal vocabulary.

This adapter is intentional anti-corruption behavior rather than a second source of truth. The external JSON aliases remain compatibility keys; the Python model field names are authoritative inside Naruon. `task_uid` continues to be the opaque public task identity and no sequential database primary key is newly exposed.

## DDD boundary

- **Bounded context:** Tasks / reply-SLA follow-up.
- **Aggregate/entity:** `TicketTask` remains the persisted task entity.
- **API value objects:** request/response Pydantic models translate between wire compatibility and task-domain language.
- **Domain service result:** `ReplySlaEscalationResult` describes evaluated email count, created task count, SLA policy hours, and escalated ticket tasks.
- **Invariant:** an API naming repair must not alter task persistence, `task_uid`, authorization scope, SLA selection, task state transitions, or existing JSON wire keys.
- **Invariant:** generic external aliases never become the internal domain vocabulary.

## Persistence and migration impact

No database table or column is renamed in this slice. `TicketTask` persistence and Alembic history are unchanged, so no data migration, foreign-key change, index rebuild, UPSERT change, lock change, or rollback migration is required. A later persisted-schema naming repair must be handled as its own migration-safe change rather than being hidden inside this API compatibility refactor.

## Verification

`backend/tests/test_tasks_api_naming_contract.py` rejects the predecessor generic internal model/service fields and verifies that the established JSON request/response keys still round-trip through aliases. The existing `backend/tests/test_tasks_api.py` suite remains the behavioral regression authority for authenticated task creation, listing, update, source scoping, and reply-SLA escalation behavior.

## Security and operability

No credential, authorization, database query authority, provider write, network route, background-worker scheduling, retention rule, or logging payload is broadened. The change preserves wire compatibility and opaque `task_uid` identity while making internal ownership explicit.
