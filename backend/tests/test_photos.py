import base64
from io import BytesIO

import pytest
from app.adapters.photos import normalize_photo
from app.domain.calendar import InvalidInput
from PIL import Image


def synthetic_photo():
    image = Image.new("RGB", (640, 320), "#abcdff")
    output = BytesIO()
    exif = Image.Exif()
    exif[270] = "synthetic source metadata"
    image.save(output, "PNG", exif=exif)
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def test_photo_is_resized_to_jpeg_without_source_metadata():
    result = normalize_photo(synthetic_photo())
    assert result.startswith("data:image/jpeg;base64,")
    image = Image.open(BytesIO(base64.b64decode(result.split(",")[1])))
    assert image.size == (256, 256) and image.format == "JPEG" and not image.getexif()
    assert normalize_photo(None) is None


@pytest.mark.parametrize(
    "photo",
    [
        "data:image/svg+xml;base64,PHN2Zz4=",
        "data:image/png;base64,bad!",
        "data:image/png;base64,bm90YW5pbWFnZQ==",
        "https://example.com/photo.png",
        "data:image/png;base64," + base64.b64encode(b"a" * (2 * 1024 * 1024 + 1)).decode("ascii"),
    ],
    ids=["svg", "bad-base64", "not-image", "remote-url", "oversized"],
)
def test_invalid_or_oversized_photo_is_rejected(photo):
    with pytest.raises(InvalidInput):
        normalize_photo(photo)
