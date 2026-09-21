# POP3 durable retry progress

Issue #1717 exposed a cross-poll starvation case that the first UIDL implementation did not cover. A bounded poll selected the highest ten unseen UIDLs. If all ten returned a standards-conforming `-ERR` from `RETR`, they remained unobserved and were selected again on the next poll. Lower valid UIDLs could therefore remain unreachable indefinitely even though each individual poll correctly continued after the rejected message.

A later audit found the same progress invariant was still incomplete for interrupted sessions. A malformed protocol response or transport failure stops the remaining network batch, but the currently attempted UIDL was returned with no durable disposition. Because candidate selection treats missing state as never attempted and prioritizes it ahead of retries, a persistently failing newest UIDL could remain first after every reconnect and keep lower fresh backlog unreachable.

## Decision

Provider UIDL remains collection identity, not email identity. Naruon persists one owner-scoped collection disposition per `(tenant_config_id, provider_uidl)`:

- `observed` means retrieval and email persistence completed; the UIDL is not selected again;
- `retryable` means a message-level collection attempt failed without proving permanent loss; `retry_after` controls when it may re-enter the candidate set.

Candidate selection prioritizes UIDLs with no durable attempt state before due retries. This is the causal property that prevents a persistent set of retryable failures from monopolizing every bounded poll while fresh backlog exists. The one-minute retry delay matches the worker's existing polling cadence; it is not a terminal-failure threshold and does not discard the UIDL.

POP3 network I/O still happens before the database session used for collection-state writes. A standards-conforming per-message `-ERR` is returned from the network phase as a retryable UIDL and is persisted only after network I/O completes. A successfully persisted message transitions the same UIDL to `observed`. Parse failures for a retrieved UIDL are also retryable rather than silently observed.

Transport loss or malformed protocol response still ends the remaining network batch because the session itself is no longer trusted. Before stopping, the currently attempted UIDL is now returned as `retryable`. This does not assert that the failure was message-specific; it records only that the provider UIDL was attempted and not observed. On the next poll it therefore cannot masquerade as never attempted and indefinitely outrank lower fresh backlog. No later UIDL in the interrupted batch is marked because no retrieval attempt was made for it.

No `DELE` is issued. The UIDL state does not replace `Message-ID`, sender-authored Date provenance, or source fingerprints.

## Source trace

- RED `5d40f83ff48e7dd9c3bf6deb93995130c5a1470a` introduces candidate-selection regressions for fresh backlog versus due/future retry state.
- Fix `7406cb63923003df2c3a5d21a0104203f78b90bc` adds retryable collection disposition, persists `retry_after`, keeps provider I/O outside the DB session, and makes never-attempted UIDLs outrank retries.
- RED `5be27e6d11e918a37dbba3d199c4015c731e63c1` proves that malformed protocol and transport interruption previously returned the attempted UIDL with no retryable disposition, allowing the same newest UIDL to remain fresh after reconnect.
- Fix `c6462af326721da39497666d78556ec8e31432dd` records only the interrupted current UIDL as retryable before halting the untrusted session; unattempted identities remain fresh.
- These repairs extend the branch-local `0019_pop3_observed_uidl` schema rather than creating another Alembic revision. Its revision identifier and parent remain non-authoritative until #1503's canonical workspace migration lineage reaches protected ancestry and #1195 is rechained after the then-current protected head.

## Acceptance boundary

Source order is not execution evidence. Before merge, the final migration-reconciled exact head still needs:

- one Alembic head after ordinary adoption of the protected workspace migration lineage;
- fresh PostgreSQL upgrade acceptance from an empty database and from the historical protected migration point;
- repeated-poll and restart acceptance with more than the per-poll cap of persistent negative `RETR` responses ahead of valid unseen mail;
- repeated reconnect acceptance where the newest attempted UIDL repeatedly triggers malformed protocol or transport interruption and lower fresh backlog still advances;
- proof that failed UIDLs remain retryable while valid backlog advances and duplicate import counts remain stable;
- the exact-head repository test, security, coverage, and independent-review gates.

UIDL-unavailable `LIST` fallback remains compatibility-only and does not claim durable eventual progress.

## Reference

Myers, J., & Rose, M. (1996). *Post Office Protocol—Version 3* (RFC 1939). Internet Engineering Task Force. https://doi.org/10.17487/RFC1939

RFC 1939 assigns message numbers within the opened maildrop, permits repeated commands in the TRANSACTION state, defines negative `-ERR` command responses, and provides UIDL as the stable provider identifier needed to distinguish messages across sessions. Those protocol properties justify keeping session message numbers out of durable identity and retaining failed UIDL attempts as retryable collection state rather than treating them as observed, deleted, or perpetually never attempted.
