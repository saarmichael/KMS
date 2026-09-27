"""Where file bytes live, keyed by their sha256.

The interface lets another store (an S3-compatible bucket, for example) replace the local
folder without touching the code that stores or serves files.
"""

import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path


class BlobStore(ABC):
    """File bytes stored under their sha256, whatever the storage behind them."""

    @abstractmethod
    def put(self, sha256: str, data: bytes) -> None:
        """Store the bytes under their hash; do nothing if the hash is already stored.

        Args:
            sha256: The hex sha256 of `data`.
            data: The file's bytes.
        """

    @abstractmethod
    def get(self, sha256: str) -> bytes:
        """Return the bytes stored under the hash.

        Args:
            sha256: The hex sha256 of the wanted bytes.

        Returns:
            The stored bytes.

        Raises:
            FileNotFoundError: Nothing is stored under this hash.
        """


class LocalBlobStore(BlobStore):
    """One flat folder, one file per hash: `<root>/<sha256>`."""

    def __init__(self, root: Path):
        """Keep the files in `root`; the folder is created on the first put."""
        self.root = root

    def put(self, sha256: str, data: bytes) -> None:
        """Write `<root>/<sha256>` in one atomic step, unless it already exists."""
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
        """Read `<root>/<sha256>`; raise FileNotFoundError if it is missing."""
        return (self.root / sha256).read_bytes()
