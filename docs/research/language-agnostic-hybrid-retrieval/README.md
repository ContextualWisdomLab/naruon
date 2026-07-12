# Language-Agnostic Hybrid Retrieval Evidence Pack

This directory preserves source research and standards evidence for
ContextualWisdomLab/naruon#981 and PR #1039. The implementation replaces
language-dependent PostgreSQL full-text search with language-agnostic hybrid
retrieval over KG-backed surfaces.

## Preserved PDF Originals

- `pdfs/bruch-gai-ingber-2023-analysis-fusion-functions-hybrid-retrieval.pdf`
  - Source: https://arxiv.org/pdf/2210.11934
  - Record: https://arxiv.org/abs/2210.11934
  - Use: grounds the TM2C2 convex-combination default and the decision to keep
    Reciprocal Rank Fusion as a configurable rank-only alternative.
- `pdfs/chen-et-al-2024-m3-embedding.pdf`
  - Source: https://aclanthology.org/2024.findings-acl.137.pdf
  - Record: https://aclanthology.org/2024.findings-acl.137/
  - License note: ACL Anthology states that materials published in or after
    2016 are licensed under Creative Commons Attribution 4.0 International.
  - Use: grounds multilingual dense retrieval and dense+sparse hybrid
    retrieval across Korean, Japanese, Chinese, Vietnamese, and other languages.
- `pdfs/cormack-clarke-buettcher-2009-reciprocal-rank-fusion.pdf`
  - Source: https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf
  - Bibliographic record:
    https://research.google/pubs/reciprocal-rank-fusion-outperforms-condorcet-and-individual-rank-learning-methods/
  - Use: grounds the RRF fallback strategy and rank constant.

## Preserved Standards Snapshots

- `standards/unicode-uax15-normalization-forms.html`
  - Source: https://www.unicode.org/reports/tr15/
  - Use: grounds NFC normalization before search matching.
- `standards/postgresql-current-pgtrgm.html`
  - Source: https://www.postgresql.org/docs/current/pgtrgm.html
  - Use: grounds `pg_trgm` character-trigram similarity, kNN distance
    operators, and GiST trigram indexes.
- `standards/postgresql-current-unaccent.html`
  - Source: https://www.postgresql.org/docs/current/unaccent.html
  - Use: grounds accent folding with an explicit dictionary argument.

## Repository Policy Notes

- Git LFS is intentionally not used. The PDF files are ordinary Git blobs.
- The largest PDF in this evidence pack is about 13 MB.
- The standards files are raw upstream HTML snapshots; `.gitattributes`
  excludes them from whitespace checks so the upstream originals stay intact.
