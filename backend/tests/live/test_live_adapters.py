"""Live checks against the real Gemini and Voyage, run with `make test-live`.

The tests run in two passes, in the order they are written. The first pass talks to the
vendors: recording is on, but into a folder that is new for every run, so every call misses and
really reaches Gemini or Voyage. The second pass repeats some of those requests and expects each
to be answered from the file the first pass wrote, without a vendor call. Run on their own, the
second-pass tests fail, because nothing has been recorded yet.
"""

import json
import logging
import math
from pathlib import Path

import pytest

from kms.ai import get_embedder, get_vision, set_embedder, set_vision
from kms.ai.gemini import GeminiVision
from kms.ai.schema import Metadata, normalise
from kms.config import get_settings
from kms.ingest.images import prepare_image

SAMPLES = Path(__file__).parents[2] / "spike" / "samples"
SCREENSHOT_PATH = SAMPLES / "screenshot.png"
NOTE_PATH = SAMPLES / "note.txt"
BRUNETTE_SENTENCE = "A brunette woman in a red coat waits at a bus stop."
UNRELATED_SENTENCE = "Quarterly tax filing deadlines for small businesses."

_settings = get_settings()
pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not (_settings.gemini_api_key and _settings.voyage_api_key),
        reason="needs GEMINI_API_KEY and VOYAGE_API_KEY",
    ),
]


@pytest.fixture(scope="session")
def recordings_dir(tmp_path_factory) -> Path:
    # A new empty folder per run, so the first pass always calls the vendors.
    return tmp_path_factory.mktemp("recordings")


@pytest.fixture
def live_provider(monkeypatch, recordings_dir):
    # The settings and the adapters are cached per process, so both are reset on the way in
    # and on the way out; otherwise the real provider would leak into other tests.
    monkeypatch.setenv("AI_PROVIDER", "real")
    monkeypatch.setenv("AI_CACHE_DIR", str(recordings_dir))
    get_settings.cache_clear()
    set_vision(None)
    set_embedder(None)
    yield
    get_settings.cache_clear()
    set_vision(None)
    set_embedder(None)


def cosine(first: list[float], second: list[float]) -> float:
    dot_product = sum(a * b for a, b in zip(first, second, strict=True))
    first_norm = math.sqrt(sum(a * a for a in first))
    second_norm = math.sqrt(sum(b * b for b in second))
    return dot_product / (first_norm * second_norm)


# --- First pass: the vendors -------------------------------------------------------------------


def test_screenshot_is_described_with_visible_text(live_provider):
    description = get_vision().describe(
        prepare_image(SCREENSHOT_PATH.read_bytes()), "image", "screenshot.png", None
    )

    metadata = normalise(description.metadata, "image")
    assert metadata.title
    assert metadata.visible_text
    assert description.model in get_settings().vision_models


def test_text_file_is_described(live_provider):
    description = get_vision().describe(
        NOTE_PATH.read_text(encoding="utf-8"), "text", "note.txt", None
    )

    # Checked on the raw answer: normalising would set it to None whatever the model said.
    assert description.metadata.image_type is None
    metadata = normalise(description.metadata, "text")
    assert metadata.title
    assert metadata.description


@pytest.mark.parametrize("model", get_settings().vision_models)
def test_every_vision_model_accepts_the_request(live_provider, model):
    # Each model alone, not through the recorder: a fallback model is otherwise only used when
    # the first is overloaded, which is when a rejected request would be hardest to debug.
    client = get_vision().inner.client
    description = GeminiVision(client, [model]).describe(
        NOTE_PATH.read_text(encoding="utf-8"), "text", "note.txt", None
    )

    assert description.model == model
    assert description.metadata.title


def test_black_hair_is_closer_to_brunette_than_to_an_unrelated_sentence(live_provider):
    embedder = get_embedder()
    [query_vector] = embedder.embed(["black hair"], "query")
    brunette_vector, unrelated_vector = embedder.embed(
        [BRUNETTE_SENTENCE, UNRELATED_SENTENCE], "document"
    )

    assert cosine(query_vector, brunette_vector) > cosine(query_vector, unrelated_vector)


def test_image_and_text_embed_to_the_configured_dimensions(live_provider):
    vectors = get_embedder().embed(
        [prepare_image(SCREENSHOT_PATH.read_bytes()), NOTE_PATH.read_text(encoding="utf-8")],
        "document",
    )

    assert len(vectors) == 2
    assert all(len(vector) == get_settings().embedding_dims for vector in vectors)


# --- Second pass: the recorder, replaying what the first pass recorded -------------------------


def test_screenshot_description_is_replayed_from_its_recording(live_provider, caplog):
    caplog.set_level(logging.INFO)
    description = get_vision().describe(
        prepare_image(SCREENSHOT_PATH.read_bytes()), "image", "screenshot.png", None
    )

    messages = [record.getMessage() for record in caplog.records]
    hits = [
        record
        for record in caplog.records
        if record.getMessage().startswith("recording_hit kind=vision ")
    ]
    assert len(hits) == 1
    recording_file = Path(hits[0].args[0])
    assert recording_file.exists()
    assert not any(message.startswith("vision_call ") for message in messages)
    recording = json.loads(recording_file.read_text())
    assert description.model == recording["model"]
    assert description.metadata == Metadata.model_validate(recording["metadata"])


def test_embeddings_are_replayed_from_their_recording(live_provider, caplog):
    caplog.set_level(logging.INFO)
    vectors = get_embedder().embed(
        [prepare_image(SCREENSHOT_PATH.read_bytes()), NOTE_PATH.read_text(encoding="utf-8")],
        "document",
    )

    messages = [record.getMessage() for record in caplog.records]
    hits = [
        record
        for record in caplog.records
        if record.getMessage().startswith("recording_hit kind=embed ")
    ]
    assert len(hits) == 1
    recording_file = Path(hits[0].args[0])
    assert recording_file.exists()
    assert not any(message.startswith("voyage_embedded ") for message in messages)
    recording = json.loads(recording_file.read_text())
    assert vectors == recording["vectors"]
