import pytest

from kms.ai import get_embedder, get_vision, recorded, set_embedder, set_vision
from kms.ai.gemini import GeminiVision
from kms.ai.interfaces import Description, PhotoDetails
from kms.ai.recorded import RecordedEmbedder, RecordedVision
from kms.ai.schema import Metadata
from kms.ai.voyage import VoyageEmbedder
from kms.config import get_settings

METADATA = Metadata(
    title="Harbour at dusk",
    description="Boats moored in a small harbour.",
    tags=["boat", "harbour"],
    visible_text="",
    image_type="photo",
)
PHOTO_DETAILS = PhotoDetails(taken_at="2024-05-01 18:30", latitude=43.3, longitude=5.4)


class StubVision:
    """Stands in for GeminiVision: counts calls and answers as the second model in its list."""

    def __init__(self, error: Exception | None = None):
        self.models = ["first-model", "second-model"]
        self.error = error
        self.calls = 0

    def describe(self, content, asset_type, filename, photo_details):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return Description(metadata=METADATA, model="second-model")


class StubEmbedder:
    """Stands in for VoyageEmbedder: counts calls and answers with one short vector per input."""

    def __init__(self):
        self.model = "voyage-test-model"
        self.dims = 2
        self.calls = 0

    def embed(self, inputs, input_type):
        self.calls += 1
        return [[0.5, float(position)] for position in range(len(inputs))]


def test_vision_second_call_is_replayed(tmp_path):
    inner = StubVision()
    vision = RecordedVision(inner, tmp_path)

    first = vision.describe(b"jpeg bytes", "image", "IMG_1.jpg", PHOTO_DETAILS)
    second = vision.describe(b"jpeg bytes", "image", "IMG_1.jpg", PHOTO_DETAILS)

    assert inner.calls == 1
    assert second == first
    assert second.model == "second-model"
    assert len(list((tmp_path / "vision").iterdir())) == 1


def test_vision_ignores_the_filename(tmp_path):
    inner = StubVision()
    vision = RecordedVision(inner, tmp_path)

    vision.describe("some notes", "text", "notes.txt", None)
    vision.describe("some notes", "text", "renamed.txt", None)

    assert inner.calls == 1


@pytest.mark.parametrize("change", ["model", "prompt version", "content", "photo details"])
def test_vision_changed_request_is_not_replayed(tmp_path, monkeypatch, change):
    inner = StubVision()
    vision = RecordedVision(inner, tmp_path)
    vision.describe(b"jpeg bytes", "image", "IMG_1.jpg", PHOTO_DETAILS)

    content = b"jpeg bytes"
    photo_details = PHOTO_DETAILS
    if change == "model":
        inner.models = ["new-first-model", "second-model"]
    elif change == "prompt version":
        monkeypatch.setattr(recorded, "PROMPT_VERSION", recorded.PROMPT_VERSION + 1)
    elif change == "content":
        content = b"other jpeg bytes"
    else:
        photo_details = None
    vision.describe(content, "image", "IMG_1.jpg", photo_details)

    assert inner.calls == 2


def test_embed_second_call_is_replayed(tmp_path):
    inner = StubEmbedder()
    embedder = RecordedEmbedder(inner, tmp_path)

    first = embedder.embed(["a note", b"image bytes"], "document")
    second = embedder.embed(["a note", b"image bytes"], "document")

    assert inner.calls == 1
    assert second == first
    assert embedder.model == inner.model


def test_embed_changed_input_type_is_not_replayed(tmp_path):
    inner = StubEmbedder()
    embedder = RecordedEmbedder(inner, tmp_path)

    embedder.embed(["red car"], "document")
    embedder.embed(["red car"], "query")

    assert inner.calls == 2


def test_failed_call_is_not_recorded(tmp_path):
    inner = StubVision(error=RuntimeError("vendor down"))
    vision = RecordedVision(inner, tmp_path)

    with pytest.raises(RuntimeError):
        vision.describe(b"jpeg bytes", "image", "IMG_1.jpg", None)

    assert not (tmp_path / "vision").exists()
    inner.error = None
    vision.describe(b"jpeg bytes", "image", "IMG_1.jpg", None)
    assert inner.calls == 2


def test_real_provider_records_only_when_cache_dir_is_set(real_provider, monkeypatch, tmp_path):
    # Dummy keys: building the clients makes no call.
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
    get_settings.cache_clear()
    assert isinstance(get_vision(), GeminiVision)
    assert isinstance(get_embedder(), VoyageEmbedder)

    monkeypatch.setenv("AI_CACHE_DIR", str(tmp_path))
    get_settings.cache_clear()
    set_vision(None)
    set_embedder(None)
    assert isinstance(get_vision(), RecordedVision)
    assert isinstance(get_embedder(), RecordedEmbedder)
