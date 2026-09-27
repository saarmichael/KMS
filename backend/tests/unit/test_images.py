import io

import pytest
from PIL import ExifTags, Image

from kms.ingest.images import prepare_image, read_photo_details


def encode(image: Image.Image, image_format: str = "JPEG", exif: Image.Exif | None = None) -> bytes:
    buffer = io.BytesIO()
    if exif is None:
        image.save(buffer, format=image_format)
    else:
        image.save(buffer, format=image_format, exif=exif)
    return buffer.getvalue()


def decode(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def photo_exif() -> Image.Exif:
    """Taken 11 Aug 2026 at 14:32, at 51°30'58.68"N 0°7'48.72"W (central London)."""
    exif = Image.Exif()
    exif.get_ifd(ExifTags.IFD.Exif)[ExifTags.Base.DateTimeOriginal] = "2026:08:11 14:32:05"
    gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
    gps[ExifTags.GPS.GPSLatitudeRef] = "N"
    gps[ExifTags.GPS.GPSLatitude] = (51.0, 30.0, 58.68)
    gps[ExifTags.GPS.GPSLongitudeRef] = "W"
    gps[ExifTags.GPS.GPSLongitude] = (0.0, 7.0, 48.72)
    return exif


@pytest.mark.parametrize("image_format", ["PNG", "WEBP"])
def test_output_is_jpeg(image_format):
    data = encode(Image.new("RGB", (40, 30), "red"), image_format)
    assert decode(prepare_image(data)).format == "JPEG"


def test_mpo_photo_prepared_as_plain_jpeg():
    buffer = io.BytesIO()
    depth_map = Image.new("RGB", (20, 15), "blue")
    Image.new("RGB", (40, 30), "red").save(
        buffer, format="MPO", save_all=True, append_images=[depth_map]
    )
    assert decode(buffer.getvalue()).format == "MPO"

    prepared = decode(prepare_image(buffer.getvalue()))
    assert prepared.format == "JPEG"
    assert prepared.size == (40, 30)


def test_large_image_downscaled_keeping_aspect():
    data = encode(Image.new("RGB", (2048, 1536), "blue"))
    assert decode(prepare_image(data)).size == (1024, 768)


def test_small_image_not_enlarged():
    data = encode(Image.new("RGB", (300, 200), "blue"))
    assert decode(prepare_image(data)).size == (300, 200)


def test_exif_rotation_applied():
    exif = Image.Exif()
    exif[ExifTags.Base.Orientation] = 6  # "rotate 90° clockwise to display"
    data = encode(Image.new("RGB", (200, 100), "green"), exif=exif)
    assert decode(prepare_image(data)).size == (100, 200)


def test_output_has_no_exif():
    data = encode(Image.new("RGB", (40, 30), "red"), exif=photo_exif())
    assert read_photo_details(data) is not None
    output = prepare_image(data)
    assert len(decode(output).getexif()) == 0
    assert read_photo_details(output) is None


def test_transparency_flattened_on_white():
    image = Image.new("RGBA", (40, 30), (255, 0, 0, 0))
    output = decode(prepare_image(encode(image, "PNG")))
    red, green, blue = output.getpixel((20, 15))
    assert min(red, green, blue) > 245


def test_same_input_gives_same_bytes():
    data = encode(Image.new("RGB", (1500, 900), "purple"))
    assert prepare_image(data) == prepare_image(data)


def test_undecodable_image_raises():
    data = encode(Image.new("RGB", (400, 300), "orange"))
    with pytest.raises(OSError):
        prepare_image(data[: len(data) // 2])


def test_photo_details_read_from_exif():
    data = encode(Image.new("RGB", (40, 30), "red"), exif=photo_exif())
    details = read_photo_details(data)
    assert details.taken_at == "2026-08-11 14:32"
    assert details.latitude == pytest.approx(51.5163, abs=1e-4)
    assert details.longitude == pytest.approx(-0.1302, abs=1e-4)


def test_no_exif_gives_none():
    assert read_photo_details(encode(Image.new("RGB", (40, 30), "red"))) is None


def test_broken_exif_gives_none():
    exif = Image.Exif()
    gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
    gps[ExifTags.GPS.GPSLatitudeRef] = "N"
    gps[ExifTags.GPS.GPSLatitude] = (51.0, 30.0)  # seconds missing
    gps[ExifTags.GPS.GPSLongitudeRef] = "W"
    gps[ExifTags.GPS.GPSLongitude] = (0.0, 7.0, 48.72)
    data = encode(Image.new("RGB", (40, 30), "red"), exif=exif)
    assert read_photo_details(data) is None
