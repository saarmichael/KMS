import io
import time
from types import SimpleNamespace

import pytest
from PIL import Image
from voyageai import error as voyage_errors

from kms.ai import get_embedder
from kms.ai.voyage import VoyageEmbedder
from kms.config import get_settings

MODEL = "voyage-test-model"
DIMS = 1024


class StubClient:
    """Stands in for voyageai.Client: records each call and answers with numbered vectors.

    Every vector is filled with its input's position across all calls, so the order of the
    returned vectors can be checked.
    """

    def __init__(self, errors: list[Exception] | None = None, vector_length: int | None = None):
        self.errors = errors or []
        self.vector_length = vector_length
        self.calls = []
        self.inputs_seen = 0

    def multimodal_embed(self, **kwargs):
        self.calls.append(kwargs)
        if self.errors:
            raise self.errors.pop(0)
        length = self.vector_length or kwargs["output_dimension"]
        embeddings = []
        for _ in kwargs["inputs"]:
            embeddings.append([float(self.inputs_seen)] * length)
            self.inputs_seen += 1
        return SimpleNamespace(embeddings=embeddings)


@pytest.fixture
def sleeps(monkeypatch):
    # The backoff sleeps through time.sleep; recording instead keeps the tests instant.
    requested = []
    monkeypatch.setattr(time, "sleep", requested.append)
    return requested


def small_jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(buffer, format="JPEG")
    return buffer.getvalue()


def positions(vectors: list[list[float]]) -> list[int]:
    return [int(vector[0]) for vector in vectors]


def test_texts_and_images_go_in_one_call_in_order(sleeps):
    client = StubClient()
    vectors = VoyageEmbedder(client, MODEL, DIMS).embed(["a note", small_jpeg()], "document")

    (call,) = client.calls
    text_input, image_input = call["inputs"]
    assert text_input == ["a note"]
    assert len(image_input) == 1
    assert isinstance(image_input[0], Image.Image)
    assert call["model"] == MODEL
    assert call["input_type"] == "document"
    assert call["output_dimension"] == DIMS
    assert positions(vectors) == [0, 1]
    assert all(len(vector) == DIMS for vector in vectors)


def test_more_inputs_than_one_call_takes_are_split_in_order(sleeps):
    client = StubClient()
    texts = [f"note {number}" for number in range(250)]
    vectors = VoyageEmbedder(client, MODEL, DIMS).embed(texts, "document")

    assert [len(call["inputs"]) for call in client.calls] == [100, 100, 50]
    sent = [piece for call in client.calls for (piece,) in call["inputs"]]
    assert sent == texts
    assert positions(vectors) == list(range(250))


def test_query_input_type_is_passed_through(sleeps):
    client = StubClient()
    VoyageEmbedder(client, MODEL, DIMS).embed(["red car"], "query")
    assert client.calls[0]["input_type"] == "query"


def test_a_transient_error_is_retried(sleeps):
    client = StubClient(errors=[voyage_errors.RateLimitError("slow down", http_status=429)])
    vectors = VoyageEmbedder(client, MODEL, DIMS).embed(["a note"], "document")
    assert len(client.calls) == 2
    assert len(sleeps) == 1
    assert len(vectors) == 1
    assert len(vectors[0]) == DIMS


def test_wrong_vector_length_is_an_error(sleeps):
    client = StubClient(vector_length=512)
    with pytest.raises(ValueError, match="length 512"):
        VoyageEmbedder(client, MODEL, DIMS).embed(["a note"], "document")


def test_empty_input_makes_no_call(sleeps):
    client = StubClient()
    assert VoyageEmbedder(client, MODEL, DIMS).embed([], "document") == []
    assert client.calls == []


def test_real_provider_builds_the_voyage_embedder(real_provider, monkeypatch):
    # A dummy key: building the client makes no call.
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
    get_settings.cache_clear()
    embedder = get_embedder()
    assert isinstance(embedder, VoyageEmbedder)
    assert embedder.model == get_settings().embedding_model
    assert embedder.dims == get_settings().embedding_dims


def test_real_provider_without_a_key_raises(real_provider, monkeypatch):
    # Empty in the environment, so a key in .env cannot fill it in.
    monkeypatch.setenv("VOYAGE_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="VOYAGE_API_KEY"):
        get_embedder()
