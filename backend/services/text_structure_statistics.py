"""Transparent text-structure counts without an inferred readability scale."""

import re
from dataclasses import dataclass

MAX_TEXT_STRUCTURE_INPUT_CHARS = 100_000
_TERMINAL_PUNCTUATION_RUN_PATTERN = re.compile(r"[.!?。！？．]+")
SEGMENTATION_CONTRACT = "whitespace-and-terminal-punctuation-runs-v2"


@dataclass(frozen=True)
class TextStructureStatistics:
    """Descriptive counts whose segmentation rule is explicit in the result."""

    character_count: int
    non_whitespace_character_count: int
    whitespace_token_count: int
    terminal_punctuation_run_count: int
    segmentation_contract: str = SEGMENTATION_CONTRACT


def measure_text_structure(text: str) -> TextStructureStatistics:
    """Measure source text without presenting punctuation runs as sentence counts.

    Tokens are whitespace-delimited and terminal punctuation is counted as contiguous
    runs. The latter deliberately does not claim sentence segmentation: periods inside
    decimals, hostnames, abbreviations, and similar text are still punctuation runs.
    These rules therefore expose transparent source statistics rather than a
    locale-invariant readability or sentence construct, particularly for CJK and other
    scripts whose lexical segmentation is not represented by spaces.
    """
    if len(text) > MAX_TEXT_STRUCTURE_INPUT_CHARS:
        raise ValueError(
            "Text structure input must not exceed "
            f"{MAX_TEXT_STRUCTURE_INPUT_CHARS} characters"
        )

    return TextStructureStatistics(
        character_count=len(text),
        non_whitespace_character_count=sum(
            1 for character in text if not character.isspace()
        ),
        whitespace_token_count=len(text.split()),
        terminal_punctuation_run_count=len(
            _TERMINAL_PUNCTUATION_RUN_PATTERN.findall(text)
        ),
    )
