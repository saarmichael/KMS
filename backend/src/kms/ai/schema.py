"""The metadata the vision model returns for one file, and how our code cleans it up.

The model's answer is validated against `Metadata`, then passed through `normalise` before it
is stored. Validation catches missing fields and wrong types; everything that can be fixed
without asking the model again (length, case, duplicates) is fixed by `normalise` instead.
"""

import re
from typing import Literal

from pydantic import BaseModel

ImageType = Literal["photo", "screenshot", "document", "diagram", "other"]

TITLE_MAX_CHARS = 120
DESCRIPTION_MAX_CHARS = 1000
VISIBLE_TEXT_MAX_CHARS = 10_000
# A tag longer than this is a sentence, and a cut sentence reads wrong, so it is dropped.
TAG_MAX_CHARS = 50
# The cap applies to the model's tags only; the fixed type tags come on top of it.
MAX_MODEL_TAGS = {"image": 20, "text": 15}

# Fixed tags that let a query naming a kind of file ("picture", "document") find it.
IMAGE_TAGS = ["image", "picture"]
IMAGE_TYPE_TAGS = {
    "photo": ["photo", "photograph"],
    "screenshot": ["screenshot"],
    "document": ["document", "scan"],
    "diagram": ["diagram", "drawing"],
    "other": [],
}
TEXT_TAGS = ["text", "text file", "document"]


class Metadata(BaseModel):
    """What the vision model says about one file.

    No length limits here on purpose: an over-long answer is truncated by `normalise`, which is
    cheaper than rejecting it and asking the model again.
    """

    title: str
    description: str
    tags: list[str]
    visible_text: str
    image_type: ImageType | None


def type_tags(asset_type: str, image_type: ImageType | None) -> list[str]:
    """The fixed tags for this kind of file, taken from its type rather than from the model."""
    if asset_type == "text":
        return list(TEXT_TAGS)
    tags = list(IMAGE_TAGS)
    if image_type is not None:
        tags.extend(IMAGE_TYPE_TAGS[image_type])
    return tags


def normalise(metadata: Metadata, asset_type: str) -> Metadata:
    """Return a cleaned copy: trimmed and truncated text, a consistent image type, tidy tags."""
    if asset_type == "text":
        image_type = None
    else:
        # An image always has a kind; when the model did not say, it is "other".
        image_type = metadata.image_type or "other"

    tags = []
    for tag in metadata.tags:
        tag = re.sub(r"\s+", " ", tag.strip().lower())
        if tag and len(tag) <= TAG_MAX_CHARS and tag not in tags:
            tags.append(tag)
    tags = tags[: MAX_MODEL_TAGS[asset_type]]

    for tag in type_tags(asset_type, image_type):
        if tag not in tags:
            tags.append(tag)

    return Metadata(
        title=metadata.title.strip()[:TITLE_MAX_CHARS],
        description=metadata.description.strip()[:DESCRIPTION_MAX_CHARS],
        tags=tags,
        visible_text=metadata.visible_text.strip()[:VISIBLE_TEXT_MAX_CHARS],
        image_type=image_type,
    )
