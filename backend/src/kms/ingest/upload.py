"""Everything the API does at upload time.

No FastAPI types here, so the HTTP endpoint and the seeder can call the same function.
The caller has already validated the collection name.
"""

import hashlib
import io
import logging
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import RowMapping

from kms.blob import get_blob_store
from kms.config import get_settings
from kms.db import get_engine, notify_asset_pending
from kms.models import assets

logger = logging.getLogger(__name__)

# Pillow's format name → the mime type stored on the asset.
ACCEPTED_IMAGE_FORMATS = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}

UNSUPPORTED_MESSAGE = (
    "Unsupported file type: only JPEG, PNG and WebP images and UTF-8 text files are accepted."
)


class FileTooLarge(Exception):
    """The file is over the upload limit; the message is shown to the user."""


class UnsupportedFileType(Exception):
    """The bytes are neither an accepted image nor UTF-8 text; the message is shown to the user."""


@dataclass(frozen=True)
class UploadResult:
    """What an upload produced.

    Attributes:
        deduplicated: True when the collection already held these bytes.
        asset: The asset's row, new or existing.
    """

    deduplicated: bool
    asset: RowMapping


def sniff(data: bytes) -> tuple[str, str]:
    """Decide the asset's type from the bytes alone, never from the filename.

    Args:
        data: The file's bytes.

    Returns:
        `(asset_type, mime)`: `("image", <image mime>)` or `("text", "text/plain")`.

    Raises:
        UnsupportedFileType: The file is empty, or neither an accepted image nor UTF-8 text.
    """
    if not data:
        raise UnsupportedFileType("The file is empty.")

    image_format = read_image_format(data)
    if image_format in ACCEPTED_IMAGE_FORMATS:
        return "image", ACCEPTED_IMAGE_FORMATS[image_format]
    # An image in another format (GIF, BMP…) is rejected, never taken for text.
    if image_format is None and is_utf8_text(data):
        return "text", "text/plain"
    raise UnsupportedFileType(UNSUPPORTED_MESSAGE)


def read_image_format(data: bytes) -> str | None:
    """Read the image format from the bytes' header.

    Args:
        data: The file's bytes.

    Returns:
        Pillow's name for the format ("JPEG", "GIF", …), or None if the bytes are no image or
        claim a pixel count too large to decode safely.
    """
    try:
        # Image.open reads only the header, so this is cheap even for a 10 MB file.
        with Image.open(io.BytesIO(data)) as image:
            return image.format
    except UnidentifiedImageError:
        return None
    except Image.DecompressionBombError:
        # The header claims a pixel count large enough to exhaust memory when decoded.
        return None


def is_utf8_text(data: bytes) -> bool:
    """Tell whether the bytes are a text file.

    Args:
        data: The file's bytes.

    Returns:
        True for strict UTF-8 (an optional byte-order mark allowed) with no NUL bytes.
    """
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return False
    # A NUL byte is valid UTF-8 but never appears in a real text file; it marks binary data.
    return "\x00" not in text


def upload(collection: str, filename: str, data: bytes) -> UploadResult:
    """Store the file and queue it, or return the asset that already holds these bytes.

    A duplicate under a new name adds that name to the existing asset's aliases.

    Args:
        collection: The collection to store the file in, already validated.
        filename: The name the file was uploaded under.
        data: The file's bytes.

    Returns:
        The asset, and whether these bytes were already in the collection.

    Raises:
        FileTooLarge: The file is over the upload limit.
        UnsupportedFileType: The bytes are neither an accepted image nor UTF-8 text.
    """
    max_bytes = get_settings().max_upload_bytes
    if len(data) > max_bytes:
        raise FileTooLarge(f"File is larger than the {max_bytes // (1024 * 1024)} MB limit.")

    asset_type, mime = sniff(data)
    sha256 = hashlib.sha256(data).hexdigest()
    get_blob_store().put(sha256, data)

    with get_engine().begin() as connection:
        # The insert is also the dedup lookup: on a (collection, sha256) clash Postgres
        # skips the row and returns nothing. A concurrent identical upload waits here for the
        # first one to commit, then skips.
        insert_new_asset = (
            insert(assets)
            .values(
                collection=collection,
                filename=filename,
                asset_type=asset_type,
                mime=mime,
                size_bytes=len(data),
                sha256=sha256,
            )
            .on_conflict_do_nothing(constraint="uq_assets_collection_sha256")
            .returning(*assets.c)
        )
        new_asset = connection.execute(insert_new_asset).mappings().first()
        if new_asset is not None:
            notify_asset_pending(connection, new_asset["id"])
            logger.info(
                "asset_uploaded asset_id=%s collection=%s asset_type=%s size_bytes=%d",
                new_asset["id"],
                collection,
                asset_type,
                len(data),
            )
            return UploadResult(deduplicated=False, asset=new_asset)

        same_bytes = (assets.c.collection == collection) & (assets.c.sha256 == sha256)
        # One statement appends the name only if it is new, so two duplicates with different
        # names arriving together cannot overwrite each other's alias.
        append_alias = (
            update(assets)
            .where(same_bytes)
            .where(assets.c.filename != filename)
            .where(~assets.c.aliases.any(filename))
            .values(aliases=func.array_append(assets.c.aliases, filename))
        )
        connection.execute(append_alias)
        existing_asset = connection.execute(select(assets).where(same_bytes)).mappings().one()
        logger.info("asset_deduplicated asset_id=%s filename=%r", existing_asset["id"], filename)
        return UploadResult(deduplicated=True, asset=existing_asset)
