"""Split a text file into overlapping pieces, each of which becomes one search unit.

Deliberately simple: fixed-size windows that end at a space. What matters here is that every
piece keeps its character offsets, so a search hit can point at the place in the file.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    """One piece of a text file.

    Attributes:
        start: Offset of the first character in the file's text.
        end: Offset just past the last character, so `text == source[start:end]`.
        text: The piece itself.
    """

    start: int
    end: int
    text: str


def chunk_text(text: str, size: int, overlap: int) -> list[Chunk]:
    """Cut a text into windows of at most `size` characters that overlap by about `overlap`.

    Each window ends at its last space so no word is cut; a window without a space is cut at
    `size`. Whitespace at a window's edges is left out of the chunk. Never raises.

    Args:
        text: The whole decoded text of the file.
        size: The longest a chunk may be, in characters.
        overlap: How many characters each window repeats from the end of the previous one.

    Returns:
        The chunks in order; empty for an empty or whitespace-only text.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            last_space = text.rfind(" ", start, end)
            if last_space > start:
                end = last_space

        # Leave out the whitespace at both edges by moving the offsets, not by editing the text.
        chunk_start = start
        chunk_end = end
        while chunk_start < chunk_end and text[chunk_start].isspace():
            chunk_start += 1
        while chunk_end > chunk_start and text[chunk_end - 1].isspace():
            chunk_end -= 1
        if chunk_start < chunk_end:
            chunks.append(Chunk(chunk_start, chunk_end, text[chunk_start:chunk_end]))

        if end == len(text):
            break
        # Step back by about the overlap, to just after a space so no word is cut at the start
        # either; without a space in the overlap, the next window starts where this one ended.
        space_in_overlap = text.find(" ", max(end - overlap, start + 1), end)
        if space_in_overlap == -1:
            start = end
        else:
            start = space_in_overlap + 1
    return chunks
