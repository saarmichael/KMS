"""Split a passage into sentences and compare vectors, to find the sentence of a passage that is
closest in meaning to a query.

Deliberately simple, like the chunker: a sentence ends at punctuation or at a line break, and
every sentence keeps its offsets so it can be pointed at in the file.
"""

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass

# A sentence ends after ".", "!" or "?" followed by whitespace, or at a line break. Notes and
# lists often have lines without punctuation, so each line stands on its own.
SENTENCE_END = re.compile(r"[.!?](?=\s)|\n")


@dataclass(frozen=True)
class Sentence:
    """One sentence of a passage.

    Attributes:
        start: Offset of the first character in the text that was split.
        end: Offset just past the last character, so `text == source[start:end]`.
        text: The sentence itself.
    """

    start: int
    end: int
    text: str


def split_sentences(text: str) -> list[Sentence]:
    """Split a text into its sentences. Never raises.

    A passage is cut from a file at a space, so its first and last sentence may be halves.
    "e.g." or "Dr." also ends a sentence; for pointing at a place in a passage, that costs little.

    Args:
        text: The text to split.

    Returns:
        The sentences in order, without the whitespace at their edges and without the pieces
        that hold no letter or digit. Empty when the text holds no words.
    """
    ends = [boundary.end() for boundary in SENTENCE_END.finditer(text)]
    ends.append(len(text))

    sentences = []
    start = 0
    for end in ends:
        # Leave out the whitespace at both edges by moving the offsets, not by editing the text.
        sentence_start = start
        sentence_end = end
        while sentence_start < sentence_end and text[sentence_start].isspace():
            sentence_start += 1
        while sentence_end > sentence_start and text[sentence_end - 1].isspace():
            sentence_end -= 1

        piece = text[sentence_start:sentence_end]
        # A line of only punctuation, such as "---", means nothing to compare.
        if any(character.isalnum() for character in piece):
            sentences.append(Sentence(sentence_start, sentence_end, piece))
        start = end
    return sentences


def cosine_similarity(first: Sequence[float], second: Sequence[float]) -> float:
    """How closely two vectors point the same way: 1.0 for the same direction. Never raises.

    Args:
        first: One vector.
        second: Another vector of the same length.

    Returns:
        The dot product over the product of the lengths; 0.0 when either vector has length
        zero, since it points nowhere.
    """
    # Both vectors come from one embedder, so their lengths are always equal.
    dot_product = sum(
        first_value * second_value for first_value, second_value in zip(first, second, strict=False)
    )
    first_length = math.sqrt(sum(value * value for value in first))
    second_length = math.sqrt(sum(value * value for value in second))
    if first_length == 0 or second_length == 0:
        return 0.0
    return dot_product / (first_length * second_length)
