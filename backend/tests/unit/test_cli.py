import io
import json

from PIL import ExifTags, Image

from kms.ai.fake_fixtures import FIXTURES
from kms.cli import describe_command, embed_command


def photo_bytes() -> bytes:
    """A small JPEG taken 11 Aug 2026 at 14:32, at 51°30'58.68"N 0°7'48.72"W (central London)."""
    exif = Image.Exif()
    exif.get_ifd(ExifTags.IFD.Exif)[ExifTags.Base.DateTimeOriginal] = "2026:08:11 14:32:05"
    gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
    gps[ExifTags.GPS.GPSLatitudeRef] = "N"
    gps[ExifTags.GPS.GPSLatitude] = (51.0, 30.0, 58.68)
    gps[ExifTags.GPS.GPSLongitudeRef] = "W"
    gps[ExifTags.GPS.GPSLongitude] = (0.0, 7.0, 48.72)
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), "red").save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def test_describe_prints_the_fixture_for_a_known_file(tmp_path, capsys):
    path = tmp_path / "packing_list.txt"
    path.write_text("Passport, charger, rain jacket.")

    assert describe_command(path) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["model"] == "fake-vision"
    assert result["photo_details"] is None
    assert result["metadata"] == FIXTURES["packing_list.txt"].model_dump()


def test_describe_passes_photo_details_for_a_photo(tmp_path, capsys):
    path = tmp_path / "IMG_2101.jpg"
    path.write_bytes(photo_bytes())

    assert describe_command(path) == 0

    photo_details = json.loads(capsys.readouterr().out)["photo_details"]
    assert photo_details["taken_at"] == "2026-08-11 14:32"
    assert round(photo_details["latitude"], 4) == 51.5163
    assert round(photo_details["longitude"], 4) == -0.1302


def test_embed_prints_one_line_per_input(tmp_path, capsys):
    note = tmp_path / "note.txt"
    # About 2,000 characters: two chunks at the default chunk size.
    note.write_text("word " * 400)
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(photo_bytes())

    assert embed_command([note, photo]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 4
    assert lines[0].startswith(f"{note} content 0 dims=")
    assert lines[1].startswith(f"{note} content 1 dims=")
    assert lines[2].startswith(f"{photo} image 0 dims=")
    assert "norm=1.0000" in lines[2]
    assert lines[3].startswith("model=fake-embedder inputs=3 seconds=")


def test_unsupported_file_is_an_error(tmp_path, capsys):
    path = tmp_path / "data.bin"
    path.write_bytes(b"\xff\xfe\x00\x01 not text")

    assert describe_command(path) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: UnsupportedFileType: ")


def test_missing_file_is_an_error(tmp_path, capsys):
    assert embed_command([tmp_path / "absent.txt"]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: FileNotFoundError: ")
