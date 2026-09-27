from kms.ingest.chunker import chunk_text

WORDS = " ".join(f"word{number}" for number in range(400))


def test_short_text_is_one_chunk():
    chunks = chunk_text("A short note about black hair.", size=100, overlap=20)
    assert [(chunk.start, chunk.end) for chunk in chunks] == [(0, 30)]


def test_empty_text_gives_no_chunks():
    assert chunk_text("", size=100, overlap=20) == []
    assert chunk_text(" \n\n\t ", size=100, overlap=20) == []


def test_offsets_slice_the_original():
    chunks = chunk_text(WORDS, size=100, overlap=20)
    assert len(chunks) > 1
    for chunk in chunks:
        assert WORDS[chunk.start : chunk.end] == chunk.text
        assert len(chunk.text) <= 100
        # No word is cut: every chunk starts and ends on a whole word.
        assert chunk.text.split()[0] in WORDS.split()
        assert chunk.text.split()[-1] in WORDS.split()


def test_chunks_overlap_and_cover_the_text():
    chunks = chunk_text(WORDS, size=100, overlap=20)
    covered = set()
    for previous, current in zip(chunks, chunks[1:], strict=False):
        assert current.start < previous.end
    for chunk in chunks:
        covered.update(range(chunk.start, chunk.end))
    for offset, character in enumerate(WORDS):
        if not character.isspace():
            assert offset in covered
