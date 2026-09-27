import pytest
from pydantic import ValidationError

from kms.ai.schema import (
    DESCRIPTION_MAX_CHARS,
    TAG_MAX_CHARS,
    TITLE_MAX_CHARS,
    VISIBLE_TEXT_MAX_CHARS,
    Metadata,
    normalise,
)


def metadata(**fields) -> Metadata:
    values = {
        "title": "Tower Bridge",
        "description": "A bridge over a river.",
        "tags": [],
        "visible_text": "",
        "image_type": "photo",
    }
    values.update(fields)
    return Metadata(**values)


def test_tags_lowercased_trimmed_deduped():
    raw = metadata(tags=["  Bridge ", "RIVER", "bridge", "Travel   Notes", "river"])
    tags = normalise(raw, "image").tags
    assert tags[:3] == ["bridge", "river", "travel notes"]


def test_overlong_and_empty_tags_dropped():
    raw = metadata(tags=["", "   ", "x" * (TAG_MAX_CHARS + 1), "x" * TAG_MAX_CHARS, "bridge"])
    tags = normalise(raw, "image").tags
    assert tags[:2] == ["x" * TAG_MAX_CHARS, "bridge"]
    assert "" not in tags
    assert "x" * (TAG_MAX_CHARS + 1) not in tags


def test_model_tags_capped_before_type_tags():
    raw = metadata(tags=[f"tag{number}" for number in range(30)], image_type="photo")
    tags = normalise(raw, "image").tags
    assert tags == [f"tag{number}" for number in range(20)] + [
        "image",
        "picture",
        "photo",
        "photograph",
    ]


@pytest.mark.parametrize(
    ("image_type", "expected"),
    [
        ("photo", ["image", "picture", "photo", "photograph"]),
        ("screenshot", ["image", "picture", "screenshot"]),
        ("document", ["image", "picture", "document", "scan"]),
        ("diagram", ["image", "picture", "diagram", "drawing"]),
        ("other", ["image", "picture"]),
    ],
)
def test_type_tags_for_each_image_type(image_type, expected):
    assert normalise(metadata(image_type=image_type), "image").tags == expected


def test_text_gets_text_type_tags_and_null_image_type():
    result = normalise(metadata(tags=["london"], image_type="screenshot"), "text")
    assert result.image_type is None
    assert result.tags == ["london", "text", "text file", "document"]


def test_type_tag_not_duplicated():
    result = normalise(metadata(tags=["Document", "contract"], image_type=None), "text")
    assert result.tags == ["document", "contract", "text", "text file"]


def test_image_with_null_image_type_becomes_other():
    result = normalise(metadata(image_type=None), "image")
    assert result.image_type == "other"
    assert result.tags == ["image", "picture"]


def test_long_fields_truncated():
    raw = metadata(
        title="  " + "t" * (TITLE_MAX_CHARS + 50),
        description="d" * (DESCRIPTION_MAX_CHARS + 50),
        visible_text="v" * (VISIBLE_TEXT_MAX_CHARS + 50),
    )
    result = normalise(raw, "image")
    assert result.title == "t" * TITLE_MAX_CHARS
    assert result.description == "d" * DESCRIPTION_MAX_CHARS
    assert result.visible_text == "v" * VISIBLE_TEXT_MAX_CHARS


def test_missing_field_raises_validation_error():
    with pytest.raises(ValidationError):
        Metadata.model_validate({"title": "t", "description": "d", "tags": [], "image_type": None})
