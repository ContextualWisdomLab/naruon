"""Transparent text-structure counts without an inferred readability scale."""

from dataclasses import dataclass
import re

MAX_TEXT_STRUCTURE_INPUT_CHARS = 100_000
_SENTENCE_TERMINATOR_PATTERN = re.compile(r"[.!?。！？．]+")
SEGMENTATION_CONTRACT = "whitespace-and-terminal-punctuation-v1"


@dataclass(frozen=True)
class TextStructureStatistics:
    """Descriptive counts whose segmentation rule is explicit in the result."""

    character_count: int
    non_whitespace_character_count: int
    whitespace_token_count: int
    sentence_boundary_count: int
    segmentation_contract: str = SEGMENTATION_CONTRACT


def measure_text_structure(text: str) -> TextStructureStatistics:
    """Measure source text without presenting the counts as a readability score.

    Tokens are whitespace-delimited and sentence boundaries are terminal punctuation
    runs. The contract is deliberately descriptive because these rules do not establish
    a locale-invariant readability construct, particularly for CJK and other scripts
    whose lexical segmentation is not represented by spaces.
    """
    if len(text) > MAX_TEXT_STRUCTURE_INPUT_CHARS:
        raise ValueError(
            f"Text structure input must not exceed {MAX_TEXT_STRUCTURE_INPUT_CHARS} characters"
        )

    return TextStructureStatistics(
        character_count=len(text),
        non_whitespace_character_count=sum(
            1 for character in text if not character.isspace()
        ),
        whitespace_token_count=len(text.split()),
        sentence_boundary_count=len(_SENTENCE_TERMINATOR_PATTERN.findall(text)),
    )
