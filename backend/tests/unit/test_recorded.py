import hashlib
import json

import pytest

from kms.ai import recorded
from kms.ai.errors import BACKGROUND_POLICY
from kms.ai.interfaces import Description, PhotoDetails
from kms.ai.prompts import PROMPT_VERSION
from kms.ai.recorded import RecordedEmbedder, RecordedVision
from kms.ai.schema import Metadata

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
        self.model = "first-model"
        self.error = error
        self.calls = 0

    def describe(self, content, asset_type, filename, photo_details, policy):
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

    def embed(self, inputs, input_type, policy):
        self.calls += 1
        return [[0.5, float(position)] for position in range(len(inputs))]


def test_vision_second_call_is_replayed(tmp_path):
    inner = StubVision()
    vision = RecordedVision(inner, tmp_path)

    first = vision.describe(b"jpeg bytes", "image", "IMG_1.jpg", PHOTO_DETAILS, BACKGROUND_POLICY)
    second = vision.describe(b"jpeg bytes", "image", "IMG_1.jpg", PHOTO_DETAILS, BACKGROUND_POLICY)

    assert inner.calls == 1
    assert second == first
    assert second.model == "second-model"
    assert len(list((tmp_path / "vision").iterdir())) == 1


def test_vision_ignores_the_filename(tmp_path):
    inner = StubVision()
    vision = RecordedVision(inner, tmp_path)

    vision.describe("some notes", "text", "notes.txt", None, BACKGROUND_POLICY)
    vision.describe("some notes", "text", "renamed.txt", None, BACKGROUND_POLICY)

    assert inner.calls == 1


@pytest.mark.parametrize("change", ["model", "prompt version", "content", "photo details"])
def test_vision_changed_request_is_not_replayed(tmp_path, monkeypatch, change):
    inner = StubVision()
    vision = RecordedVision(inner, tmp_path)
    vision.describe(b"jpeg bytes", "image", "IMG_1.jpg", PHOTO_DETAILS, BACKGROUND_POLICY)

    content = b"jpeg bytes"
    photo_details = PHOTO_DETAILS
    if change == "model":
        inner.models = ["new-first-model", "second-model"]
        inner.model = "new-first-model"
    elif change == "prompt version":
        monkeypatch.setattr(recorded, "PROMPT_VERSION", recorded.PROMPT_VERSION + 1)
    elif change == "content":
        content = b"other jpeg bytes"
    else:
        photo_details = None
    vision.describe(content, "image", "IMG_1.jpg", photo_details, BACKGROUND_POLICY)

    assert inner.calls == 2


def test_vision_recording_key_is_unchanged(tmp_path):
    # The request as it was keyed before the wrapper read `inner.model`, built from the first
    # model in the list; recordings made then must still be found.
    old_request = {
        "model": "first-model",
        "prompt_version": PROMPT_VERSION,
        "asset_type": "text",
        "content_sha256": hashlib.sha256(b"some notes").hexdigest(),
        "photo_details": None,
    }
    path = recorded.recording_path(tmp_path, "vision", old_request)
    recorded.write_recording(path, {"model": "first-model", "metadata": METADATA.model_dump()})
    inner = StubVision()
    vision = RecordedVision(inner, tmp_path)

    description = vision.describe("some notes", "text", "notes.txt", None, BACKGROUND_POLICY)

    assert inner.calls == 0
    assert description == Description(metadata=METADATA, model="first-model")


def test_embed_second_call_is_replayed(tmp_path):
    inner = StubEmbedder()
    embedder = RecordedEmbedder(inner, tmp_path)

    first = embedder.embed(["a note", b"image bytes"], "document", BACKGROUND_POLICY)
    second = embedder.embed(["a note", b"image bytes"], "document", BACKGROUND_POLICY)

    assert inner.calls == 1
    assert second == first
    assert embedder.model == inner.model


def test_embed_changed_input_type_is_not_replayed(tmp_path):
    inner = StubEmbedder()
    embedder = RecordedEmbedder(inner, tmp_path)

    embedder.embed(["red car"], "document", BACKGROUND_POLICY)
    embedder.embed(["red car"], "query", BACKGROUND_POLICY)

    assert inner.calls == 2


def test_recording_is_written_whole(tmp_path):
    path = tmp_path / "embed" / "request.json"

    recorded.write_recording(path, {"vectors": [[0.1, 0.2]]})

    assert json.loads(path.read_text()) == {"vectors": [[0.1, 0.2]]}
    assert [file.name for file in path.parent.iterdir()] == ["request.json"]


def test_failed_call_is_not_recorded(tmp_path):
    inner = StubVision(error=RuntimeError("vendor down"))
    vision = RecordedVision(inner, tmp_path)

    with pytest.raises(RuntimeError):
        vision.describe(b"jpeg bytes", "image", "IMG_1.jpg", None, BACKGROUND_POLICY)

    assert not (tmp_path / "vision").exists()
    inner.error = None
    vision.describe(b"jpeg bytes", "image", "IMG_1.jpg", None, BACKGROUND_POLICY)
    assert inner.calls == 2
