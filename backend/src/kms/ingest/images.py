"""What the worker does to an image before the AI calls.

The stored original is never changed. The vision model and the embedder get a smaller, upright
JPEG copy without metadata; the date and place the photo carried are read from the original and
passed to the vision model separately, as plain values.
"""

import io
import logging

from PIL import ExifTags, Image, ImageOps

from kms.ai.interfaces import PhotoDetails

logger = logging.getLogger(__name__)

IMAGE_MAX_SIDE = 1024
# High enough that text in screenshots stays sharp.
JPEG_QUALITY = 90


def prepare_image(data: bytes) -> bytes:
    """Return the copy of an image that the AI calls see.

    The copy is upright, flattened to RGB with transparency on white, at most 1024 px on its
    longest side, and a JPEG without metadata. The same bytes always give the same copy.

    Args:
        data: The uploaded image, as stored.

    Returns:
        The JPEG bytes.

    Raises:
        OSError: The bytes cannot be decoded (Pillow's own error).
    """
    image = Image.open(io.BytesIO(data))
    # Phones often store a photo sideways with a tag saying how to turn it; turn the pixels
    # instead, so the models see what the user sees.
    image = ImageOps.exif_transpose(image)

    has_transparency = image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    )
    if has_transparency:
        # JPEG has no transparency; a plain conversion would turn transparent areas black.
        with_alpha = image.convert("RGBA")
        image = Image.new("RGB", with_alpha.size, "white")
        image.paste(with_alpha, mask=with_alpha.getchannel("A"))
    else:
        image = image.convert("RGB")

    # Shrinks in place, keeping the proportions; never enlarges.
    image.thumbnail((IMAGE_MAX_SIDE, IMAGE_MAX_SIDE))

    output = io.BytesIO()
    # Saved without the original's metadata: the vendors need none of it.
    image.save(output, format="JPEG", quality=JPEG_QUALITY)
    return output.getvalue()


def read_photo_details(data: bytes) -> PhotoDetails | None:
    """Read when and where a photo was taken from its own metadata.

    Never raises: metadata comes in many broken variants, and an image whose metadata cannot be
    read is still a good image.

    Args:
        data: The uploaded image, as stored, before its metadata is stripped.

    Returns:
        The date taken and the position; either may be None. None when the image carries
        neither, or when its metadata cannot be read.
    """
    try:
        exif = Image.open(io.BytesIO(data)).getexif()

        taken_at = exif.get_ifd(ExifTags.IFD.Exif).get(ExifTags.Base.DateTimeOriginal)
        if taken_at is not None:
            # EXIF writes "2026:08:11 14:32:05"; the model reads "2026-08-11 14:32" more easily.
            date, time = taken_at.strip().split(" ")
            taken_at = date.replace(":", "-") + " " + time[:5]

        gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
        coordinates = []
        for value_tag, reference_tag in (
            (ExifTags.GPS.GPSLatitude, ExifTags.GPS.GPSLatitudeRef),
            (ExifTags.GPS.GPSLongitude, ExifTags.GPS.GPSLongitudeRef),
        ):
            if value_tag not in gps or reference_tag not in gps:
                coordinates.append(None)
                continue
            # Stored as degrees, minutes and seconds; south and west are negative.
            degrees, minutes, seconds = gps[value_tag]
            coordinate = float(degrees) + float(minutes) / 60 + float(seconds) / 3600
            if gps[reference_tag] in ("S", "W"):
                coordinate = -coordinate
            coordinates.append(coordinate)
        latitude, longitude = coordinates
    except Exception as error:
        logger.info("photo_details_unreadable error=%r", f"{type(error).__name__}: {error}")
        return None

    # A position needs both halves.
    if latitude is None or longitude is None:
        latitude = longitude = None
    if taken_at is None and latitude is None:
        return None
    return PhotoDetails(taken_at=taken_at, latitude=latitude, longitude=longitude)
