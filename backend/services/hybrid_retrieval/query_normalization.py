"""Query-side text normalization for language-agnostic search.

Normalization contract (must mirror the SQL-side
``search_normalized_text`` function created in migration
0010_language_agnostic_search):

1. Unicode NFC composition (UAX #15) — Vietnamese and Korean text
   arrives in mixed composed/decomposed forms depending on the source
   platform; both sides must compose before comparison.
2. Accent folding and lowercasing happen in SQL (``unaccent`` +
   ``lower``) so indexed document expressions and the bound query
   parameter go through the identical code path.

Only whitespace shaping and NFC are done in Python; everything that
depends on PostgreSQL runtime behavior stays in SQL.
"""

import unicodedata

_MAX_QUERY_CHARACTER_LENGTH = 1000


def normalize_search_text(raw_text: str) -> str:
    """Compose the query to NFC and collapse insignificant whitespace."""
    composed_text = unicodedata.normalize("NFC", raw_text)
    collapsed_text = " ".join(composed_text.split())
    return collapsed_text[:_MAX_QUERY_CHARACTER_LENGTH]
