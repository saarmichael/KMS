import logging
from collections.abc import Awaitable, Callable
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from sqlalchemy.engine import Connection, RowMapping

from kms.api.schemas import COLLECTION_NAME_PATTERN, Asset, AssetList, UploadResponse
from kms.blob import get_blob_store
from kms.config import get_settings
from kms.db import get_engine, notify_asset_pending
from kms.ingest.upload import FileTooLarge, UnsupportedFileType, upload
from kms.models import assets

logger = logging.getLogger(__name__)

router = APIRouter()

# Room for the multipart boundaries, headers and the collection field around the file's bytes.
MULTIPART_OVERHEAD_BYTES = 64 * 1024


async def reject_oversized_upload(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Refuse an upload whose declared size is over the limit, before its body is read.

    FastAPI reads the whole multipart body before the upload handler runs, so the handler's own
    size check only comes after a large file has been received in full.

    Args:
        request: The incoming request.
        call_next: The rest of the app, called when the request may pass.

    Returns:
        A 413 with the handler's `{"detail": ...}` when a `POST /api/assets` declares a
        `Content-Length` over the limit plus the form's overhead; otherwise the app's response.
        A request without a readable `Content-Length` passes, and the handler checks its size.
    """
    if request.method != "POST" or request.url.path != "/api/assets":
        return await call_next(request)
    try:
        declared_bytes = int(request.headers.get("content-length", ""))
    except ValueError:
        return await call_next(request)

    max_bytes = get_settings().max_upload_bytes
    if declared_bytes <= max_bytes + MULTIPART_OVERHEAD_BYTES:
        return await call_next(request)
    # The filename is inside the body, which is never read.
    reason = f"declares {declared_bytes} bytes"
    logger.info("upload_rejected filename=%r status=413 reason=%r", None, reason)
    return JSONResponse(
        status_code=413,
        content={"detail": f"File is larger than the {max_bytes // (1024 * 1024)} MB limit."},
    )


def load_asset_or_404(connection: Connection, asset_id: UUID) -> RowMapping:
    """Load one asset's row.

    Args:
        connection: An open database connection.
        asset_id: The asset to load.

    Returns:
        The asset's row.

    Raises:
        HTTPException: 404 if there is no such asset.
    """
    asset_row = connection.execute(select(assets).where(assets.c.id == asset_id)).mappings().first()
    if asset_row is None:
        raise HTTPException(status_code=404, detail="Asset not found.")
    return asset_row


@router.post("/api/assets", status_code=202)
def upload_asset(
    file: UploadFile,
    collection: Annotated[str, Form(pattern=COLLECTION_NAME_PATTERN)],
    response: Response,
) -> UploadResponse:
    """Store one file in a collection: 202 for a new file, 200 for bytes it already holds.

    Args:
        file: The uploaded file.
        collection: The collection to store it in.
        response: The outgoing response, so a duplicate can turn its status into 200.

    Returns:
        The asset, and whether its bytes were already stored.

    Raises:
        HTTPException: 413 if the file is over the size limit, 415 if its type is not accepted.
    """
    # One byte past the limit is enough to know the file is too large, without reading all of it.
    data = file.file.read(get_settings().max_upload_bytes + 1)
    try:
        result = upload(collection, file.filename, data)
    except FileTooLarge as error:
        logger.info("upload_rejected filename=%r status=413 reason=%r", file.filename, str(error))
        raise HTTPException(status_code=413, detail=str(error)) from None
    except UnsupportedFileType as error:
        logger.info("upload_rejected filename=%r status=415 reason=%r", file.filename, str(error))
        raise HTTPException(status_code=415, detail=str(error)) from None

    if result.deduplicated:
        response.status_code = 200
    return UploadResponse(deduplicated=result.deduplicated, asset=Asset.from_row(result.asset))


@router.get("/api/assets")
def list_assets(
    collection: Annotated[str, Query(pattern=COLLECTION_NAME_PATTERN)],
) -> AssetList:
    """Every asset of a collection, in any status, newest first.

    Args:
        collection: The collection to list.
    """
    newest_first = (
        select(assets).where(assets.c.collection == collection).order_by(assets.c.created_at.desc())
    )
    with get_engine().connect() as connection:
        asset_rows = connection.execute(newest_first).mappings().all()
    return AssetList(assets=[Asset.from_row(asset_row) for asset_row in asset_rows])


@router.get("/api/assets/{asset_id}")
def get_asset(asset_id: UUID) -> Asset:
    """One asset, in any status.

    Raises:
        HTTPException: 404 if there is no such asset.
    """
    with get_engine().connect() as connection:
        asset_row = load_asset_or_404(connection, asset_id)
    return Asset.from_row(asset_row)


@router.get("/api/assets/{asset_id}/file")
def get_asset_file(asset_id: UUID) -> Response:
    """The file's bytes, cached by the browser for good: an asset's bytes never change.

    Args:
        asset_id: The asset whose file to send.

    Returns:
        The bytes, to be shown inline, with the file's sha256 as ETag.

    Raises:
        HTTPException: 404 if there is no such asset.
    """
    with get_engine().connect() as connection:
        asset_row = load_asset_or_404(connection, asset_id)
    try:
        data = get_blob_store().get(asset_row["sha256"])
    except FileNotFoundError:
        # The row exists but its bytes do not: the volume lost them. Still a 500, but a
        # findable one.
        logger.error("blob_missing asset_id=%s sha256=%s", asset_id, asset_row["sha256"])
        raise

    # Upload accepts only UTF-8 text, so the charset is always true.
    content_type = asset_row["mime"]
    if asset_row["asset_type"] == "text":
        content_type = "text/plain; charset=utf-8"

    # An HTTP header carries only Latin-1, so a non-ASCII name goes in the percent-encoded form.
    filename = asset_row["filename"]
    # Quotes, backslashes and spaces also need encoding, not just non-ASCII.
    if quote(filename) == filename:
        content_disposition = f'inline; filename="{filename}"'
    else:
        content_disposition = f"inline; filename*=utf-8''{quote(filename)}"

    headers = {
        "ETag": f'"{asset_row["sha256"]}"',
        "Cache-Control": "public, max-age=31536000, immutable",
        "Content-Disposition": content_disposition,
    }
    return Response(content=data, media_type=content_type, headers=headers)


@router.post("/api/assets/{asset_id}/retry")
def retry_asset(asset_id: UUID) -> Asset:
    """Put a failed asset back in the queue with a fresh attempt count.

    Args:
        asset_id: The asset to retry.

    Returns:
        The asset, now pending.

    Raises:
        HTTPException: 404 if there is no such asset, 409 if it is not failed.
    """
    # The status check is part of the update, so a double click cannot re-queue an asset
    # that a worker has already picked up.
    reset_failed_asset = (
        update(assets)
        .where(assets.c.id == asset_id)
        .where(assets.c.status == "failed")
        .values(status="pending", attempts=0, error=None, started_at=None)
        .returning(*assets.c)
    )
    with get_engine().begin() as connection:
        retried_row = connection.execute(reset_failed_asset).mappings().first()
        if retried_row is None:
            asset_row = load_asset_or_404(connection, asset_id)
            raise HTTPException(
                status_code=409,
                detail=f"Only a failed asset can be retried; this one is {asset_row['status']}.",
            )
        notify_asset_pending(connection, asset_id)
    logger.info("asset_retried asset_id=%s", asset_id)
    return Asset.from_row(retried_row)
