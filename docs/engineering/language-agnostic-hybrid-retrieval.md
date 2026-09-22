# Language-agnostic hybrid retrieval (G6) — design & research grounding

Roadmap: ContextualWisdomLab/naruon#981 (Phase P0) + the hybrid-search
bullet of ContextualWisdomLab/naruon#975. Disciplines: **G6**
(language-agnostic), **SEAM** (don't productionize stopgaps), **CP-1**
(KG is the product), **CP-2** (surface evidence + calibrated
confidence).

## Proposed storage repair (2026-09-05)

[ADR-0020](../adr/0020-full-document-trigram-storage.md) records a forward
full-content GIN replacement for the four whole-document GiST indexes. Large,
diverse inputs can exceed GiST's leaf-size limit even at maximum `siglen`.
The candidate preserves normalized text, scores, ordering, and scope, but GIN
does not accelerate distance-only top-k queries. Keep this change Draft until
representative latency, lock/build cost, and current-head hosted gates are
verified; unit data is not production performance evidence. See the
[real PostgreSQL receipt](../doctoring/search_trigram_storage.md).

## What changed

Context Search (`POST /api/search`) previously scored with
`ts_rank_cd(to_tsvector('english', …))` minus a raw cosine distance —
a language-DEPENDENT tokenizer (fails CJK: the tokenizer cliff), an
unbounded score fusion on incomparable scales, and coverage limited to
`email_records` + `email_attachments`.

It now runs two channels per query and fuses them per candidate:

| Channel | Mechanism | Language handling |
|---|---|---|
| Lexical | Exact `pg_trgm` `word_similarity` over `search_normalized_text(document)`, ordered by `<->>`; the Proposed GIN storage repair does not provide indexed kNN | Character n-grams — no tokenizer, no per-language config; NFC + `unaccent` + `lower` fold both sides |
| Dense | pgvector cosine over stored multilingual embeddings | Multilingual embedding space (provider-routed) |

Search surfaces (naruon#975): `email_records` (subject+body),
`email_attachments.content`, `content_segments.safe_text_content`,
`project_graph_objects.title || ' ' || summary`. Segment / project
object / attachment evidence maps back to its parent email; the
response reports `result_kind` (strongest evidence) and
`evidence_kinds` (all matching surfaces) alongside a bounded [0,1]
`score` (CP-2: resolved connection + evidence + calibrated
confidence).

`search_normalized_text` (migration `0010_language_agnostic_search`) =
`lower(unaccent('public.unaccent'::regdictionary, normalize(text, NFC)))`
as an `IMMUTABLE` SQL wrapper (the documented pattern for making
`unaccent` indexable). NFC composition makes decomposed Vietnamese /
Korean input (macOS file names, some webmail clients emit NFD) match
composed storage; `unaccent` makes `hop ban nhac` match `họp ban
nhạc`. The Python query path applies the identical NFC step
through the pinned `rankweave` dependency re-exported by
`services/hybrid_retrieval/__init__.py`.

Degradation: with no LLM provider (or embedding failure) search runs
lexical-only instead of failing — the previous behavior returned HTTP
400 when no provider was configured.

## Fusion: TM2C2 default, RRF alternative (the seam)

The roadmap issue named RRF; the current literature says a bounded
convex combination is strictly better, so the fusion is a **pluggable
seam** (`services/hybrid_retrieval/score_fusion.py`,
`SEARCH_FUSION_STRATEGY`):

- **Default `convex_combination` (TM2C2)** — Bruch, Gai & Ingber
  (2023) show a convex combination of *theoretically* min-max
  normalized scores outperforms RRF in-domain AND out-of-domain, is
  robust for α ∈ [0.6, 0.8] with no training data, and — unlike rank
  fusion — preserves the score distribution (Lipschitz continuity;
  their desiderata: monotonicity, homogeneity, boundedness, Lipschitz
  continuity, sample efficiency). We use α = 0.7
  (`SEARCH_FUSION_SEMANTIC_WEIGHT`) and theoretical bounds
  `word_similarity ∈ [0,1]`, cosine distance ∈ [0,2] — no
  data-dependent normalization, stable across queries.
- **`reciprocal_rank_fusion`** — Cormack, Clarke & Büttcher (2009),
  η = 60 (`SEARCH_RRF_RANK_CONSTANT`); kept for channels that expose
  only ranks (future learned-sparse / external channels) and as the
  non-parametric fallback.

A channel absent for a candidate contributes its theoretical minimum
(0), not an imputed value. Results below
`SEARCH_MINIMUM_FUSED_SCORE` (default 0.05) are dropped so pure-kNN
noise does not surface on no-match queries.

## Research & standards grounding

Verified sources (content read and confirmed this session):

1. **Bruch, Gai & Ingber (2023).** *An Analysis of Fusion Functions
   for Hybrid Retrieval.* ACM TOIS 42(1). arXiv:2210.11934. — TM2C2 >
   RRF (their Table 2/3/4); RRF parameter sensitivity; normalization
   choice immaterial for convex combination; α ∈ [0.6, 0.8] robust
   range; fusion desiderata.
2. **Chen, Xiao, Zhang, Luo, Lian & Liu (2024).** *M3-Embedding:
   Multi-Linguality, Multi-Functionality, Multi-Granularity Text
   Embeddings Through Self-Knowledge Distillation.* Findings of ACL
   2024. arXiv:2402.03216. — multilingual dense retrieval across 100+
   languages incl. KO/JA/ZH/VI (MIRACL nDCG@10: ko 69.9, ja 72.8, zh
   62.7; MKQA R@100: vi 76.6, ko 71.6); Dense+Sparse hybrid > each
   single channel — grounds the two-channel architecture and the
   future learned-sparse channel.
3. **Cormack, Clarke & Büttcher (2009).** *Reciprocal Rank Fusion
   outperforms Condorcet and individual Rank Learning Methods.* SIGIR
   2009. — RRF definition, η = 60.
4. **UAX #15, Unicode Normalization Forms** (Unicode Consortium) — NFC
   composition; PostgreSQL 13+ `normalize(text, NFC)`.
5. **PostgreSQL 16 documentation** (PostgreSQL License): F.35
   `pg_trgm` (word_similarity, `<->>` GiST kNN, `siglen`), F.50
   `unaccent` (STABLE-by-search-path; explicit-dictionary immutable
   wrapper pattern).

PDF archival note (governance: attach source research evidence):
source PDFs for Bruch et al. 2023, Chen et al. 2024, and Cormack et al.
2009 are preserved under
`docs/research/language-agnostic-hybrid-retrieval/pdfs/`. The same
evidence pack preserves upstream snapshots of UAX #15 and the current
PostgreSQL `pg_trgm` / `unaccent` documentation under
`docs/research/language-agnostic-hybrid-retrieval/standards/`. Git LFS
is intentionally not used.

## Why not …

- **`to_tsvector` with per-language configs** — G6 violation; CJK has
  no config that works without a morphological analyzer, and
  analyzers (Kiwi/Nori) are the documented performance cliff.
- **pg_bigm** — better bigram recall for CJK but not shipped in the
  pgvector/pgvector:pg16 image nor Ubuntu's postgres packages;
  pg_trgm is a core contrib module. The lexical channel is a seam —
  pg_bigm or a SPLADE-style learned-sparse channel (pgvector
  `sparsevec`) can be added without touching fusion.
- **SQL-side fusion (UNION + ORDER BY)** — the old approach; fusing in
  Python keeps the fusion function pure, unit-tested, and
  strategy-swappable. Index-served lexical ordering does not hold for the
  Proposed GIN storage repair; the measured performance gate remains open.

## OSMU spin-off assessment (one source, multi use)

The earlier extraction assessment is historical. Current source imports fusion
and query normalization from the pinned `rankweave` package and re-exports them
through `services/hybrid_retrieval/__init__.py`. Naruon owns the schema-bound
`retrieval_channels.py` statements and migrations, not a copied fusion runtime.
This storage repair changes no RankWeave contract or model-routing authority.

## Operational notes

- Migration `0010_language_agnostic_search` creates extensions
  `pg_trgm` + `unaccent` (both PostgreSQL-licensed contrib, present in
  the deploy image), the `search_normalized_text` function, and four
  GiST expression indexes. Downgrade drops indexes + function, keeps
  extensions.
- The Proposed `0020_search_trigram_storage` revision replaces those four
  indexes with GIN in the existing migration transaction. Its downgrade keeps
  the corrected indexes so newly valid large records do not make rollback fail.
  Published revision 0010 remains unchanged; plan storage and lock time before
  any production migration.
- The channel SQL expressions in
  `services/hybrid_retrieval/retrieval_channels.py` must stay
  textually identical to the indexed expressions.
- Fixed in passing: revision id `0008_attachment_parser_audit_metadata`
  (38 chars) overflowed `alembic_version.version_num` VARCHAR(32) —
  `alembic upgrade head` failed on every fresh database. Shortened to
  `0008_attachment_parser_audit`; no deployed database can have been
  stamped with the long id (the stamp itself could not be written), so
  the rename is safe. A guard test now enforces ≤ 32 chars.
- `content_segments` / `project_graph_objects` have no embedding
  columns yet; they are lexical-only until the batch-embedding work
  (routed via contextual-orchestrator, naruon#973) adds them. The
  fusion treats the missing channel as evidence-absent, not zero-worthy.
