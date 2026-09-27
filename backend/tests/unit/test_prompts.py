import pytest

from kms.ai.interfaces import PhotoDetails
from kms.ai.prompts import IMAGE_PROMPT, build_image_prompt


def test_image_prompt_names_date_and_place_when_given():
    prompt = build_image_prompt(
        PhotoDetails(taken_at="2024-05-01 18:30", latitude=43.7384, longitude=7.4246)
    )
    assert prompt.startswith(IMAGE_PROMPT)
    assert "2024-05-01 18:30" in prompt
    assert "latitude 43.7384" in prompt
    assert "longitude 7.4246" in prompt


@pytest.mark.parametrize(
    "photo_details",
    [
        None,
        PhotoDetails(taken_at=None, latitude=None, longitude=None),
        # A position needs both coordinates.
        PhotoDetails(taken_at=None, latitude=43.7384, longitude=None),
    ],
)
def test_image_prompt_leaves_them_out_when_absent(photo_details):
    assert build_image_prompt(photo_details) == IMAGE_PROMPT
