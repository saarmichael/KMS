import io

import pytest
from PIL import Image

from kms.ingest.upload import UnsupportedFileType, sniff


def image_bytes(image_format: str) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(buffer, format=image_format)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("image_format", "mime"),
    [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")],
)
def test_accepted_image_formats_are_images(image_format, mime):
    assert sniff(image_bytes(image_format)) == ("image", mime)


def test_utf8_text_is_text():
    assert sniff("Café notes, black hair.\n".encode()) == ("text", "text/plain")
    assert sniff(b"\xef\xbb\xbfwith a byte-order mark") == ("text", "text/plain")


@pytest.mark.parametrize(
    "data",
    [bytes(range(256)), "café".encode("latin-1"), b"valid utf-8 but \x00 inside"],
    ids=["binary", "latin-1", "nul-byte"],
)
def test_binary_and_non_utf8_are_rejected(data):
    with pytest.raises(UnsupportedFileType):
        sniff(data)


def test_unaccepted_image_format_is_rejected():
    with pytest.raises(UnsupportedFileType):
        sniff(image_bytes("GIF"))


def test_empty_file_is_rejected():
    with pytest.raises(UnsupportedFileType, match="empty"):
        sniff(b"")


def test_decompression_bomb_is_rejected(monkeypatch):
    # Pillow refuses images over twice MAX_IMAGE_PIXELS; at 4 the 4x4 test image (16) is a "bomb".
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 4)
    with pytest.raises(UnsupportedFileType):
        sniff(image_bytes("PNG"))
