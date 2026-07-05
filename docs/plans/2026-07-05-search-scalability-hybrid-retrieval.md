# Search Scalability: Hybrid Retrieval Reshape

> **For agentic workers:** REQUIRED SUB-SKILL: use
> superpowers:executing-plans / subagent-driven-development and the repo's
> RED/GREEN discipline. This is a behavior-affecting change to a core read
> path (`/api/search`), so land it test-first with Postgres-backed evidence,
> not against mocks alone.

**Status:** Proposal (evidence-backed). Not yet implemented.

## Problem

`/api/search` does a full sequential scan on every query and cannot use any
index — including indexes that "look" correct. This is the single largest
scaling cliff in the product: search latency grows linearly with mailbox size
and will fall over at enterprise volumes.

The root cause is **query shape**, not just missing indexes.
`backend/api/search.py:_search_score` builds:

```python
fts_score = func.ts_rank_cd(
    func.to_tsvector("english", text_column),
    func.plainto_tsquery("english", query),
)
vector_distance = embedding_column.cosine_distance(query_embedding)
return fts_score - vector_distance          # composite, used in ORDER BY
```

There is **no `@@` text-match predicate** and the FTS and vector scores are
fused into a single `ORDER BY` expression. Both facts independently defeat
indexing:

- A GIN full-text index only accelerates a `@@` match filter (or `@@`-gated
  rank). With no `@@` in the `WHERE`, Postgres must compute `ts_rank_cd` for
  **every** row.
- An ANN index (`ivfflat`/`hnsw`) only accelerates a **pure** distance
  `ORDER BY embedding <=> q LIMIT k`. Fusing it into `ts_rank_cd - distance`
  makes the ORDER BY non-ANN-eligible.

There is also a correctness cliff: the composite score is an unnormalized
subtraction of incomparable scales (`ts_rank_cd` magnitude vs cosine distance
`[0,2]`), so ranking is dominated by whichever term happens to be larger, and
`embedding.py:fit_embedding_vector` zero-pads/truncates vectors to 1536 dims,
silently degrading vector quality across models.

## Evidence (pgvector 0.8.2, `EXPLAIN (COSTS OFF)`, 5k rows)

**(A) Current shape, and (A2) the SAME query after adding GIN + HNSW indexes —
both seq-scan; the indexes are never used:**

```
Limit
  ->  Sort  (Sort Key: (ts_rank_cd(...) - (embedding <=> $q)) DESC)
        ->  Seq Scan on email_records
```

**(B) FTS-gated with a `@@` predicate → GIN index is used:**

```
Limit
  ->  Sort  (Sort Key: ts_rank_cd(...) DESC)
        ->  Bitmap Heap Scan on email_records
              Recheck Cond: (to_tsvector('english', body) @@ plainto_tsquery('english', $q))
              ->  Bitmap Index Scan on ix_email_records_body_fts
```

**(C) Pure ANN `ORDER BY embedding <=> q LIMIT` → HNSW index is used:**

```
Limit
  ->  Index Scan using ix_email_records_embedding_hnsw on email_records
        Order By: (embedding <=> $q)
```

Conclusion: adding indexes without reshaping the query is a no-op for this
endpoint. The reshape and the indexes must land together.

## Design: hybrid retrieval + fuse

Replace the single composite-ORDER-BY scan with the standard two-arm hybrid
retrieval, per table (`email_records`, `email_attachments`):

1. **Lexical arm** — `WHERE to_tsvector('english', <col>) @@ plainto_tsquery('english', q)`
   `ORDER BY ts_rank_cd(...) DESC LIMIT k` (uses GIN).
2. **Vector arm** (when an embedding is available) — `ORDER BY embedding <=> q
   LIMIT k` (uses HNSW).
3. **Fuse** the two candidate sets in the app with a normalized score
   (min-max or Reciprocal Rank Fusion; RRF avoids scale mismatch entirely),
   then apply owner (`user_id`/`organization_id`) filters and the existing
   dedupe/snippet post-processing.

Keep the current full-text-only fallback (`search.py:202`) when the embedding
provider errors. Preserve exact ABAC owner scoping on both arms.

## Migration (lands with the reshape, not before)

`backend/alembic/versions/0010_search_fts_vector_indexes.py`, dialect-guarded
(`postgresql` only), pgvector-version-aware (`hnsw` when `vector >= 0.5`, else
`ivfflat WITH (lists=100)`), created `CONCURRENTLY IF NOT EXISTS` inside
`op.get_context().autocommit_block()` so a large `email_records` build does not
lock writes:

- `ix_email_records_body_fts` — `gin (to_tsvector('english', body))`
- `ix_email_records_embedding_hnsw` — `hnsw (embedding vector_cosine_ops)`
- `ix_email_attachments_content_fts` — `gin (to_tsvector('english', content))`
- `ix_email_attachments_embedding_hnsw` — `hnsw (embedding vector_cosine_ops)`

## Tasks

- [ ] RED: add a `@pytest.mark.postgres` integration test that seeds
  `email_records`, runs migration `0010`, and asserts (via `EXPLAIN`) the
  lexical arm uses `ix_email_records_body_fts` and the vector arm uses the HNSW
  index. It fails today because both arms seq-scan and the indexes do not exist.
- [ ] Add migration `0010_search_fts_vector_indexes.py` as specified above.
- [ ] Reshape `build_email_search_stmt` / `build_attachment_search_stmt` into
  the lexical + vector two-arm form; add an RRF/normalized fuse step.
- [ ] Update the existing mock-based `tests/test_search.py` assertions to the
  new statement shape; keep owner-scope and fallback tests green.
- [ ] GREEN: Postgres integration test shows index usage; mock unit tests pass.
- [ ] Follow-up (separate PR): fix `embedding.py:fit_embedding_vector` to stop
  padding/truncating to 1536 and standardize a first-class embedding dimension;
  optional cross-encoder rerank after fusion.

## Why this matters

This is a P0 "trust-at-scale" blocker: an enterprise mailbox import turns
search from milliseconds into a full-table scan per keystroke. The fix is
well-scoped (indexes + a standard hybrid-retrieval reshape), but it changes
ranking and result membership, so it must go through RED/GREEN with
Postgres-backed evidence rather than a naive index migration that the planner
would ignore.
