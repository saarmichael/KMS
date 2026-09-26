from typing import Annotated

from fastapi import APIRouter, Path, Response
from sqlalchemy import delete, func, select

from kms.api.schemas import COLLECTION_NAME_PATTERN, Collection, CollectionList
from kms.db import get_engine
from kms.models import assets

router = APIRouter()


@router.get("/api/collections")
def list_collections() -> CollectionList:
    """Every collection that holds at least one asset, with its asset count, sorted by name."""
    counts_by_name = (
        select(assets.c.collection, func.count().label("asset_count"))
        .group_by(assets.c.collection)
        .order_by(assets.c.collection)
    )
    with get_engine().connect() as connection:
        count_rows = connection.execute(counts_by_name).mappings().all()
    return CollectionList(
        collections=[
            Collection(name=count_row["collection"], asset_count=count_row["asset_count"])
            for count_row in count_rows
        ]
    )


@router.delete("/api/collections/{name}", status_code=204)
def delete_collection(name: Annotated[str, Path(pattern=COLLECTION_NAME_PATTERN)]) -> Response:
    """Delete the collection's assets; their search units go with them. Files stay on disk."""
    with get_engine().begin() as connection:
        connection.execute(delete(assets).where(assets.c.collection == name))
    # Also 204 when nothing was deleted: deleting twice is not an error.
    return Response(status_code=204)
