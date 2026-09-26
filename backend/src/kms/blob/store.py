"""Where file bytes live, keyed by their sha256.

The interface exists so that an S3-compatible store can replace the local volume later
(design doc, Deployment) without touching the code that stores or serves files.
"""

import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path


class BlobStore(ABC):
    @abstractmethod
    def put(self, sha256: str, data: bytes) -> None:
        """Store the bytes under their hash; do nothing if the hash is already stored."""

    @abstractmethod
    def get(self, sha256: str) -> bytes:
        """Return the bytes stored under the hash; raise FileNotFoundError if there are none."""


class LocalBlobStore(BlobStore):
    """One flat folder, one file per hash: `<root>/<sha256>`."""

    def __init__(self, root: Path):
        self.root = root

    def put(self, sha256: str, data: bytes) -> None:
        final_path = self.root / sha256
        if final_path.exists():
            return
        self.root.mkdir(parents=True, exist_ok=True)
        # Write under a unique temporary name, then rename in one step: a reader never sees a
        # half-written file, and two uploads of the same bytes at once both succeed.
        temporary_path = self.root / f"{sha256}.tmp-{uuid.uuid4().hex}"
        temporary_path.write_bytes(data)
        os.replace(temporary_path, final_path)

    def get(self, sha256: str) -> bytes:
        return (self.root / sha256).read_bytes()
