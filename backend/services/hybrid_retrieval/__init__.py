"""Language-agnostic hybrid retrieval (G6 discipline).

This package is the stable retrieval seam for Context Search: a dense
multilingual-embedding channel and a language-agnostic lexical channel
(character trigrams via pg_trgm) fused per candidate by a pluggable
fusion function (TM2C2 convex combination by default, RRF as the
non-parametric alternative).

Research grounding is documented in
docs/engineering/language-agnostic-hybrid-retrieval.md.

The fusion and query-normalization primitives are provided by the standalone
``rankweave`` package (an OSMU spin-off extracted from these modules); this
package stays the naruon-side seam and re-exports them, so
``retrieval_channels`` and other callers keep importing from
``services.hybrid_retrieval``.
"""

from rankweave import (
    COSINE_DISTANCE_THEORETICAL_BOUNDS,
    WORD_SIMILARITY_THEORETICAL_BOUNDS,
    FusionSettings,
    convex_combination_score,
    fuse_channel_scores,
    normalize_search_text,
    reciprocal_rank_fusion_score,
    theoretical_min_max_normalize,
)

__all__ = [
    "COSINE_DISTANCE_THEORETICAL_BOUNDS",
    "WORD_SIMILARITY_THEORETICAL_BOUNDS",
    "FusionSettings",
    "convex_combination_score",
    "fuse_channel_scores",
    "normalize_search_text",
    "reciprocal_rank_fusion_score",
    "theoretical_min_max_normalize",
]
