import pytest

from kms.search.sentences import cosine_similarity, split_sentences


def sentence_texts(text):
    return [sentence.text for sentence in split_sentences(text)]


def test_splits_after_sentence_punctuation():
    text = "The tram climbs the hill. Is it steep? Very! The view is worth it"

    assert sentence_texts(text) == [
        "The tram climbs the hill.",
        "Is it steep?",
        "Very!",
        "The view is worth it",
    ]


def test_splits_at_line_breaks():
    text = "Shopping list\n- bread\n- custard tarts"

    assert sentence_texts(text) == ["Shopping list", "- bread", "- custard tarts"]


def test_offsets_point_back_into_the_text():
    text = "  First line.\nSecond one! Third, with 3.5 litres.  \n\nLast"

    sentences = split_sentences(text)

    assert len(sentences) == 4
    for sentence in sentences:
        assert text[sentence.start : sentence.end] == sentence.text


def test_edge_whitespace_is_left_out():
    text = "   The harbour at dusk.   \n  "

    sentences = split_sentences(text)

    assert len(sentences) == 1
    assert sentences[0].text == "The harbour at dusk."
    assert (sentences[0].start, sentences[0].end) == (3, 23)


def test_pieces_without_words_are_dropped():
    text = "Chapter one\n---\n...\nIt begins."

    assert sentence_texts(text) == ["Chapter one", "It begins."]


@pytest.mark.parametrize("text", ["", "   \n\t ", "--- !!! ..."])
def test_text_without_words_gives_no_sentences(text):
    assert split_sentences(text) == []


def test_cosine_of_same_direction_is_one():
    assert cosine_similarity([1.0, 2.0, 2.0], [2.0, 4.0, 4.0]) == pytest.approx(1.0)


def test_cosine_of_zero_vector_is_zero():
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0
