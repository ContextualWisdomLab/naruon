# Email-model reconciliation — one source of truth (ADR)

Roadmap: the "Reconcile the multi-account email model to one source of
truth" bullet of ContextualWisdomLab/naruon#975 (Phase P0).
Disciplines: **SEAM** (don't cement scaffolding), **CP-1** (KG is the
product), **CP-5** (multi-account binding is an identity concern).

## Decision

**`email_records` is the single email source of truth.** Message
identity and dedup stay on `message_id` + `fingerprint`
(email_dedupe_service); thread identity stays exclusively with
`services/threading_service.py`. The account/provider *configuration*
plane is `tenant_configs` (surfaced by `/api/accounts`),
`caldav_accounts`, and `webdav_accounts`.

The abandoned parallel account-centric email model — `User`
(user_accounts), `Account` (provider_accounts), `EmailRaw`
(email_raws), `EmailMessage` (email_messages), `EmailInstance`
(email_instances), `EmailThread` (email_threads), `EmailThreadEdge`
(email_thread_edges) — is **removed** (migration
`0011_email_model_reconciliation`, guard tests in
`tests/test_email_model_reconciliation.py`).

## Evidence for removal

Verified on develop at the time of removal:

- **Zero importers**: no backend, test, script, or doc referenced any
  of the seven classes or table names (the only textual matches were
  Python's stdlib `email.message.EmailMessage`).
- **Never migrated**: no alembic revision creates these tables, and
  Alembic history is authoritative (`CLAUDE.md`); `bootstrap_db.py`
  does not create them either. They only ever materialized in dev/test
  databases via `Base.metadata.create_all`, so the drop migration is a
  defensive dev-database cleanup and managed databases are unaffected.
- **Duplicated live behavior**: canonical-content dedup
  (`canonical_hash`) duplicates the live `fingerprint` path, and
  `email_threads`/`email_thread_edges` duplicated (and would have
  competed with) `threading_service.py`, which is the only thread-id
  assignment owner.

## Why not "finish" the parallel model instead

The parallel model encoded a real target (JMAP-style separation of
account, message, and per-account instance) but as a **second email
store**, which violates the reconciliation goal itself: every consumer
(search, threading, KG extraction, tickets, reply tracking) reads
`email_records`, so completing the parallel store would have forked
the platform's data plane and re-imposed the scattered-context problem
naruon exists to remove (CP-1). Multi-account requirements land
differently:

- **Standards reference (P2 target shape)**: JMAP — RFC 8620 (core:
  the `Account` object as a scoping concept distinct from user
  credentials) and RFC 8621 (mail: `Email`/`Mailbox`/`Thread` objects
  scoped to accounts) — informs the *vocabulary* for the P2
  multi-account binding: accounts scope access and provenance; they do
  not fork message storage. RFC 5322 §3.6.4 keeps `Message-ID` as the
  cross-account correlation key (same message fetched via two accounts
  correlates by Message-ID + content fingerprint, exactly what the
  live dedup does).
- **P2 lands in the KG, not in a second table family**: "N email
  accounts → one identity" (platform plan §5b problem 1, CP-5) is an
  *identity-resolution* concern — reversible merge/split with
  evidence and calibrated confidence — modeled as first-class KG
  entities on the P2 typed-entity foundation, referencing
  `email_records` rows as evidence. Account provenance needed at P2
  (which configured account ingested a message) attaches to
  `email_records` (a nullable `source_account_uid` column or a slim
  provenance table keyed by opaque uid), which is additive and does
  not require a parallel store.

## Consequences

- `Base.metadata` shrinks by seven never-deployed tables; dev/test
  databases converge with managed schema.
- Guard tests fail any PR that reintroduces the retired classes or
  table names.
- The P2 multi-account work starts from one unambiguous foundation:
  `email_records` + config plane + KG identity entities.
