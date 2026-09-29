import math
from pathlib import PurePath

import pytest
from pydantic import ValidationError

from kms.ai import get_vision
from kms.ai.errors import BACKGROUND_POLICY
from kms.ai.fake import FakeEmbedder, FakeVision
from kms.ai.fake_fixtures import FIXTURES
from kms.ai.gemini import GeminiVision
from kms.config import get_settings

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def cosine(first: list[float], second: list[float]) -> float:
    return sum(a * b for a, b in zip(first, second, strict=True))


def test_fake_vision_returns_fixture_for_known_filename():
    description = FakeVision().describe(
        b"any bytes", "image", "IMG_2101.jpg", None, BACKGROUND_POLICY
    )
    assert description.metadata == FIXTURES["IMG_2101.jpg"]
    assert description.model == "fake-vision"


@pytest.mark.parametrize(("asset_type", "image_type"), [("image", "other"), ("text", None)])
def test_fake_vision_generic_metadata_for_unknown_file(asset_type, image_type):
    metadata = (
        FakeVision()
        .describe("content", asset_type, "unknown_file.bin", None, BACKGROUND_POLICY)
        .metadata
    )
    assert metadata.title == "unknown_file.bin"
    assert metadata.description
    assert metadata.image_type == image_type


def test_fake_vision_invalid_marker_raises_validation_error():
    with pytest.raises(ValidationError):
        FakeVision().describe("content", "text", "notes_invalid.txt", None, BACKGROUND_POLICY)


def test_fixtures_match_their_file_kind():
    for filename, metadata in FIXTURES.items():
        if PurePath(filename).suffix.lower() in IMAGE_SUFFIXES:
            assert metadata.image_type is not None, filename
        else:
            assert metadata.image_type is None, filename


def test_fake_embedder_is_deterministic():
    embedder = FakeEmbedder(1024)
    inputs = ["black hair", b"\x89PNG image bytes"]
    assert embedder.embed(inputs, "document", BACKGROUND_POLICY) == embedder.embed(
        inputs, "query", BACKGROUND_POLICY
    )


def test_fake_embedder_unit_length_and_dims():
    vectors = FakeEmbedder(1024).embed(
        ["black hair", "", "!!! ...", b"bytes"], "document", BACKGROUND_POLICY
    )
    for vector in vectors:
        assert len(vector) == 1024
        assert math.isclose(math.sqrt(sum(value * value for value in vector)), 1.0)


def test_fake_embedder_shared_words_are_closer():
    query, shared, synonym = FakeEmbedder(1024).embed(
        ["black hair", "black hair salon", "brunette"], "document", BACKGROUND_POLICY
    )
    assert cosine(query, shared) > cosine(query, synonym)


def test_fake_embedder_images_differ_by_bytes():
    first, second = FakeEmbedder(1024).embed(
        [b"image one", b"image two"], "document", BACKGROUND_POLICY
    )
    assert first != second


def test_real_provider_builds_gemini_vision(real_provider, monkeypatch):
    # A dummy key: building the client makes no call.
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()
    assert isinstance(get_vision(), GeminiVision)
