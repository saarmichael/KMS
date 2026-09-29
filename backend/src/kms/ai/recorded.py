"""Record and replay: every successful vendor answer is kept as a JSON file and reused.

A request is turned into a fingerprint; the same request later reads the file instead of
calling the vendor. The files stay on the machine that made them, so an emptied
database replays the same answers without spending quota.
"""

import hashlib
import json
import logging
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Literal

from kms.ai.errors import RetryPolicy
from kms.ai.gemini import GeminiVision
from kms.ai.interfaces import Description, Embedder, PhotoDetails, Vision
from kms.ai.prompts import PROMPT_VERSION
from kms.ai.schema import Metadata
from kms.ai.voyage import VoyageEmbedder

logger = logging.getLogger(__name__)


def recording_path(cache_dir: Path, kind: str, request: dict) -> Path:
    """Return the file that holds the answer to one request.

    Args:
        cache_dir: The folder all recordings live under.
        kind: "vision" or "embed"; each kind has its own subfolder.
        request: Everything that decides the answer. It must be JSON-serialisable.

    Returns:
        `cache_dir/kind/<sha256 of the request as sorted JSON>.json`. The file may not exist.
    """
    # Sorted keys, so the same request always gives the same text and the same hash.
    request_text = json.dumps(request, sort_keys=True)
    request_hash = hashlib.sha256(request_text.encode()).hexdigest()
    return cache_dir / kind / f"{request_hash}.json"


def write_recording(path: Path, recording: dict) -> None:
    """Write one recording as JSON, so that a reader only ever sees the whole file.

    A crash or a second thread mid-write would otherwise leave half a file, which every later
    read of the same request would fail on. The JSON goes to a temporary file in the same
    folder first, then a rename puts it in place in one step.

    Args:
        path: The recording's file, from `recording_path`; its folder is created if missing.
        recording: The answer to keep. It must be JSON-serialisable.

    Raises:
        OSError: The folder or the file could not be written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, suffix=".tmp", delete=False
    ) as temporary_file:
        json.dump(recording, temporary_file)
    os.replace(temporary_file.name, path)


class RecordedVision(Vision):
    """Replays Gemini's answer for a file it has described before, and records new ones.

    Attributes:
        inner: The real adapter, called when there is no recording yet.
        cache_dir: The folder all recordings live under.
    """

    def __init__(self, inner: GeminiVision, cache_dir: Path):
        """Create the wrapper.

        Args:
            inner: The real adapter to call on a miss.
            cache_dir: The folder all recordings live under.
        """
        self.inner = inner
        self.cache_dir = cache_dir

    def describe(
        self,
        content: bytes | str,
        asset_type: str,
        filename: str,
        photo_details: PhotoDetails | None,
        policy: RetryPolicy,
    ) -> Description:
        """Return the recorded description, or ask Gemini and record its answer.

        Args:
            content: The prepared JPEG bytes for an image, the summary text for a text file.
            asset_type: "image" or "text".
            filename: Passed on to Gemini's logs; not part of the fingerprint, because Gemini
                never sees it.
            photo_details: When and where the photo was taken.
            policy: Passed on to Gemini on a miss; not part of the fingerprint, because it does
                not change the answer.

        Returns:
            The metadata, validated but not normalised, and the model that answered.

        Raises:
            pydantic.ValidationError: A recording does not match the schema; delete the file to
                record it again.
            Exception: Any error from the real adapter, unchanged; nothing is recorded.
        """
        if isinstance(content, str):
            content_bytes = content.encode()
        else:
            content_bytes = content
        photo_details_dict = None
        if photo_details is not None:
            photo_details_dict = asdict(photo_details)
        # Only the first model counts: a new primary model should describe the files again,
        # while the fallbacks only answer when it is overloaded.
        request = {
            "model": self.inner.models[0],
            "prompt_version": PROMPT_VERSION,
            "asset_type": asset_type,
            "content_sha256": hashlib.sha256(content_bytes).hexdigest(),
            "photo_details": photo_details_dict,
        }
        path = recording_path(self.cache_dir, "vision", request)

        if path.exists():
            logger.info("recording_hit kind=vision file=%s", path)
            recording = json.loads(path.read_text())
            metadata = Metadata.model_validate(recording["metadata"])
            return Description(metadata=metadata, model=recording["model"])

        description = self.inner.describe(content, asset_type, filename, photo_details, policy)
        recording = {"model": description.model, "metadata": description.metadata.model_dump()}
        write_recording(path, recording)
        return description


class RecordedEmbedder(Embedder):
    """Replays Voyage's vectors for inputs it has embedded before, and records new ones.

    Attributes:
        inner: The real embedder, called when there is no recording yet.
        cache_dir: The folder all recordings live under.
        model: The inner embedder's model, so callers see the model that made the vectors.
    """

    def __init__(self, inner: VoyageEmbedder, cache_dir: Path):
        """Create the wrapper.

        Args:
            inner: The real embedder to call on a miss.
            cache_dir: The folder all recordings live under.
        """
        self.inner = inner
        self.cache_dir = cache_dir
        self.model = inner.model

    def embed(
        self,
        inputs: list[str | bytes],
        input_type: Literal["document", "query"],
        policy: RetryPolicy,
    ) -> list[list[float]]:
        """Return the recorded vectors, or ask Voyage and record its answer.

        Args:
            inputs: A str is embedded as text, bytes as an image.
            input_type: "document" for stored content, "query" for a search query.
            policy: Passed on to Voyage on a miss; not part of the fingerprint, because it does
                not change the answer.

        Returns:
            One vector per input, in the same order.

        Raises:
            json.JSONDecodeError: A recording is not valid JSON; delete the file to record it
                again.
            Exception: Any error from the real embedder, unchanged; nothing is recorded.
        """
        # The kind is part of the fingerprint: a text and an image with the same bytes are
        # different inputs.
        fingerprints = []
        for item in inputs:
            if isinstance(item, bytes):
                fingerprints.append(["image", hashlib.sha256(item).hexdigest()])
            else:
                fingerprints.append(["text", hashlib.sha256(item.encode()).hexdigest()])
        request = {
            "model": self.inner.model,
            "dims": self.inner.dims,
            "input_type": input_type,
            "inputs": fingerprints,
        }
        path = recording_path(self.cache_dir, "embed", request)

        if path.exists():
            logger.info("recording_hit kind=embed file=%s", path)
            recording = json.loads(path.read_text())
            return recording["vectors"]

        vectors = self.inner.embed(inputs, input_type, policy)
        write_recording(path, {"vectors": vectors})
        return vectors
