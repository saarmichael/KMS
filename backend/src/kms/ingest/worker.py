"""Turn a pending asset into a searchable one.

Postgres is the queue. A worker claims one row and commits the claim at once, so no
transaction stays open during the slow AI calls; the results are written later in one
transaction, so an asset is either fully processed or untouched. A claim is a lease: if the
worker dies, the reaper puts the asset back after LEASE_MINUTES.
"""

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import RowMapping

from kms.ai import get_embedder, get_vision
from kms.ai.interfaces import PhotoDetails
from kms.ai.schema import Metadata, normalise
from kms.blob import get_blob_store
from kms.config import get_settings
from kms.db import get_engine
from kms.ingest.chunker import Chunk, chunk_text
from kms.ingest.images import prepare_image, read_photo_details
from kms.ingest.summary_source import choose_summary_source
from kms.models import assets, search_units

logger = logging.getLogger(__name__)

ERROR_MAX_CHARS = 1000


@dataclass(frozen=True)
class Unit:
    """One search unit, ready to be embedded and stored.

    Attributes:
        kind: "metadata", "filename", "content" or "image".
        unit_index: The unit's position among the asset's units of the same kind.
        start_char: For a content unit, where its chunk starts in the file; otherwise None.
        end_char: For a content unit, where its chunk ends in the file; otherwise None.
        body: The text the keyword index sees; None for the image unit.
        embed_input: What the embedder sees: the text, or the prepared JPEG for the image unit.
    """

    kind: str
    unit_index: int
    start_char: int | None
    end_char: int | None
    body: str | None
    embed_input: str | bytes


def claim_one() -> RowMapping | None:
    """Take the oldest pending asset and mark it as being processed.

    The claim is committed at once. SKIP LOCKED lets any number of workers claim side by side:
    a row another worker is claiming right now is skipped, not waited on.

    Returns:
        The claimed row, with its new `started_at` and `attempts`, or None if nothing is pending.
    """
    oldest_pending = (
        select(assets.c.id)
        .where(assets.c.status == "pending")
        .order_by(assets.c.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
        .scalar_subquery()
    )
    claim = (
        update(assets)
        .where(assets.c.id == oldest_pending)
        .values(status="processing", started_at=func.now(), attempts=assets.c.attempts + 1)
        .returning(*assets.c)
    )
    with get_engine().begin() as connection:
        asset = connection.execute(claim).mappings().first()
    if asset is not None:
        logger.info("asset_claimed asset_id=%s attempt=%s", asset["id"], asset["attempts"])
    return asset


@dataclass(frozen=True)
class PreparedFile:
    """A file made ready for the AI calls.

    Attributes:
        content: What the vision model sees: the prepared JPEG for an image, the summary text
            for a text file.
        photo_details: When and where a photo was taken; None for a text file and for an image
            that carries neither.
        prepared_image: The prepared JPEG for an image; None for a text file.
        chunks: The text file's chunks; empty for an image.
    """

    content: bytes | str
    photo_details: PhotoDetails | None
    prepared_image: bytes | None
    chunks: list[Chunk]


def prepare_file(data: bytes, asset_type: str) -> PreparedFile:
    """Prepare a file's bytes for the vision and embedding calls.

    The worker and the command line both prepare through here, so the same file always sends
    the same inputs and a recorded call is replayed.

    Args:
        data: The file's bytes.
        asset_type: "image" or "text".

    Returns:
        The vision model's input, the photo details, the prepared image and the chunks.

    Raises:
        OSError: An image's bytes cannot be decoded (raised by `prepare_image`).
        UnicodeDecodeError: A text file is not valid UTF-8.
    """
    settings = get_settings()
    if asset_type == "image":
        prepared_image = prepare_image(data)
        return PreparedFile(
            content=prepared_image,
            photo_details=read_photo_details(data),
            prepared_image=prepared_image,
            chunks=[],
        )

    # "utf-8-sig" drops a byte-order mark, so offsets match the text a browser shows.
    text = data.decode("utf-8-sig")
    chunks = chunk_text(text, settings.chunk_size_chars, settings.chunk_overlap_chars)
    summary_source = choose_summary_source(text, settings.summary_token_budget)
    return PreparedFile(
        content=summary_source.text_for_description(text),
        photo_details=None,
        prepared_image=None,
        chunks=chunks,
    )


def process(asset: RowMapping) -> None:
    """Describe, split and embed one claimed asset, then commit the results.

    Args:
        asset: The row returned by `claim_one`.

    Raises:
        Exception: Whatever a step raises (missing blob, undecodable image, invalid AI answer,
            vendor error); the caller records it as a failed attempt.
    """
    data = get_blob_store().get(asset["sha256"])
    prepared = prepare_file(data, asset["asset_type"])

    description = get_vision().describe(
        prepared.content, asset["asset_type"], asset["filename"], prepared.photo_details
    )
    logger.info("asset_described asset_id=%s model=%s", asset["id"], description.model)
    metadata = normalise(description.metadata, asset["asset_type"])

    units = build_units(
        asset["asset_type"], asset["filename"], metadata, prepared.prepared_image, prepared.chunks
    )
    vectors = get_embedder().embed([unit.embed_input for unit in units], "document")
    commit_ready(asset, metadata, description.model, units, vectors)


def metadata_body(metadata: Metadata) -> str:
    """Return the text of an asset's metadata unit.

    The same metadata always gives the same text, so a recorded embedding call can be replayed.

    Args:
        metadata: The normalised metadata.

    Returns:
        Title, description, the tags and the visible text if there is any, one block each.
    """
    blocks = [metadata.title, metadata.description, "tags: " + ", ".join(metadata.tags)]
    if metadata.visible_text:
        blocks.append(metadata.visible_text)
    return "\n\n".join(blocks)


def filename_body(filename: str) -> str:
    """Return the text of an asset's filename unit.

    Postgres keeps a bare file name such as "notes-lisbon.txt" as one token, so a search for
    "lisbon" would miss it. The name's words are written out after it so each one is indexed.

    Args:
        filename: The name the asset was first uploaded under.

    Returns:
        The full name, then its words: every run of letters and digits, in order.
    """
    words = re.findall(r"[^\W_]+", filename)
    return " ".join([filename, *words])


def build_units(
    asset_type: str,
    filename: str,
    metadata: Metadata,
    prepared_image: bytes | None,
    chunks: list[Chunk],
) -> list[Unit]:
    """Return every search unit of one asset, in the order they are embedded.

    Args:
        asset_type: "image" or "text".
        filename: The name the asset was first uploaded under.
        metadata: The normalised metadata.
        prepared_image: The JPEG the AI calls see, for an image; None for a text file.
        chunks: The text file's chunks; empty for an image.

    Returns:
        The metadata unit, the filename unit, then the image unit for an image or one content
        unit per chunk.
    """
    body = metadata_body(metadata)
    name_body = filename_body(filename)
    units = [
        Unit("metadata", 0, None, None, body, body),
        Unit("filename", 0, None, None, name_body, name_body),
    ]
    if asset_type == "image":
        units.append(Unit("image", 0, None, None, None, prepared_image))
    for index, chunk in enumerate(chunks):
        units.append(Unit("content", index, chunk.start, chunk.end, chunk.text, chunk.text))
    return units


def commit_ready(
    asset: RowMapping,
    metadata: Metadata,
    vision_model: str,
    units: list[Unit],
    vectors: list[list[float]],
) -> bool:
    """Write the metadata, the units and `ready` in one transaction.

    Only while this worker still holds the lease: if the reaper reset the asset and another
    worker claimed it, `started_at` has changed and nothing is written.

    Args:
        asset: The row returned by `claim_one`.
        metadata: The normalised metadata.
        vision_model: The id of the model that wrote `metadata`.
        units: The asset's units, in the order they were embedded.
        vectors: One vector per unit, in the same order.

    Returns:
        True when committed, False when the lease was lost.
    """
    # The model answers "" for a text file, which has no pixels to read; stored as null, so a
    # text file reads as "no visible text" rather than "an image with none".
    if asset["asset_type"] == "text":
        visible_text = None
    else:
        visible_text = metadata.visible_text
    mark_ready = (
        update(assets)
        .where(assets.c.id == asset["id"])
        .where(assets.c.status == "processing")
        .where(assets.c.started_at == asset["started_at"])
        .values(
            status="ready",
            error=None,
            title=metadata.title,
            description=metadata.description,
            tags=metadata.tags,
            visible_text=visible_text,
            image_type=metadata.image_type,
            vision_model=vision_model,
        )
    )
    unit_rows = []
    for unit, vector in zip(units, vectors, strict=True):
        unit_rows.append(
            {
                "asset_id": asset["id"],
                "collection": asset["collection"],
                "kind": unit.kind,
                "unit_index": unit.unit_index,
                "start_char": unit.start_char,
                "end_char": unit.end_char,
                "body": unit.body,
                "embedding": vector,
                "embedding_model": get_embedder().model,
            }
        )

    with get_engine().begin() as connection:
        if connection.execute(mark_ready).rowcount == 0:
            logger.warning("lease_lost asset_id=%s attempt=%s", asset["id"], asset["attempts"])
            return False
        connection.execute(insert(search_units), unit_rows)

    duration = datetime.now(UTC) - asset["started_at"]
    logger.info(
        "asset_ready asset_id=%s attempt=%s duration_ms=%d units=%d",
        asset["id"],
        asset["attempts"],
        duration.total_seconds() * 1000,
        len(units),
    )
    return True


def record_failure(asset: RowMapping, error: Exception) -> str:
    """Record a failed attempt: back to pending, or failed once the attempts are used up.

    Args:
        asset: The row returned by `claim_one`.
        error: What went wrong; stored as "<ErrorClass>: <message>", cut to 1,000 characters.

    Returns:
        The asset's new status, "pending" or "failed", or "lease_lost" when another worker
        holds the asset now and nothing was written.
    """
    message = f"{type(error).__name__}: {error}"[:ERROR_MAX_CHARS]
    if asset["attempts"] >= get_settings().max_attempts:
        new_status = "failed"
    else:
        new_status = "pending"

    mark_failed_attempt = (
        update(assets)
        .where(assets.c.id == asset["id"])
        .where(assets.c.status == "processing")
        .where(assets.c.started_at == asset["started_at"])
        .values(status=new_status, error=message, started_at=None)
    )
    with get_engine().begin() as connection:
        if connection.execute(mark_failed_attempt).rowcount == 0:
            logger.warning("lease_lost asset_id=%s attempt=%s", asset["id"], asset["attempts"])
            return "lease_lost"

    event = "asset_failed" if new_status == "failed" else "attempt_failed"
    logger.warning(
        "%s asset_id=%s attempt=%s error=%r", event, asset["id"], asset["attempts"], message
    )
    return new_status


def reaper() -> int:
    """Release assets whose worker stopped without finishing: its lease has expired.

    An expired lease counts as an attempt, so an asset that keeps killing its worker cannot
    loop forever: once its attempts are used up it becomes failed instead of pending.

    Returns:
        How many assets were released or failed.
    """
    settings = get_settings()
    expired = (assets.c.status == "processing") & (
        assets.c.started_at < func.now() - timedelta(minutes=settings.lease_minutes)
    )
    fail_used_up = (
        update(assets)
        .where(expired)
        .where(assets.c.attempts >= settings.max_attempts)
        .values(
            status="failed",
            started_at=None,
            error=f"Processing did not finish within the lease {settings.max_attempts} times.",
        )
        .returning(assets.c.id, assets.c.attempts)
    )
    release = (
        update(assets)
        .where(expired)
        .values(status="pending", started_at=None)
        .returning(assets.c.id, assets.c.attempts)
    )
    with get_engine().begin() as connection:
        failed_rows = connection.execute(fail_used_up).all()
        released_rows = connection.execute(release).all()

    for row in failed_rows:
        logger.warning("lease_expired asset_id=%s attempt=%s status=failed", row.id, row.attempts)
    for row in released_rows:
        logger.warning("lease_expired asset_id=%s attempt=%s status=pending", row.id, row.attempts)
    return len(failed_rows) + len(released_rows)


def run_once() -> bool:
    """Claim and process one asset, recording a failed attempt if anything goes wrong.

    Returns:
        True when an asset was claimed, False when nothing was pending.
    """
    asset = claim_one()
    if asset is None:
        return False
    try:
        process(asset)
    except Exception as error:
        # Any failure of this one asset is recorded against it; the worker itself carries on.
        record_failure(asset, error)
    return True
