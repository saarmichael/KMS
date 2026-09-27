import pytest

from kms.ingest.summary_source import MapReduce, choose_summary_source


def test_short_text_uses_whole_file():
    text = "a short note"
    source = choose_summary_source(text, token_budget=10)
    assert source.text_for_description(text) == text


def test_long_text_uses_head():
    # A budget of 10 tokens is 40 characters.
    text = "x" * 40 + "y" * 10
    source = choose_summary_source(text, token_budget=10)
    assert source.text_for_description(text) == "x" * 40


def test_map_reduce_is_not_implemented():
    with pytest.raises(NotImplementedError):
        MapReduce().text_for_description("any text")
