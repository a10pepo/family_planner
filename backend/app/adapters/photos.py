import base64
import binascii
import warnings
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app.domain.calendar import InvalidInput


def normalize_photo(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        prefix, payload = value.split(",", 1)
        if prefix not in {
            "data:image/jpeg;base64",
            "data:image/png;base64",
            "data:image/webp;base64",
        }:
            raise ValueError("format")
        binary = base64.b64decode(payload, validate=True)
        if len(binary) > 2 * 1024 * 1024:
            raise ValueError("size")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(binary)) as image:
                if (
                    image.format not in {"JPEG", "PNG", "WEBP"}
                    or image.width * image.height > 20_000_000
                ):
                    raise ValueError("image")
                image.load()
                oriented = ImageOps.exif_transpose(image)
                rgba = ImageOps.fit(oriented.convert("RGBA"), (256, 256), Image.Resampling.LANCZOS)
                background = Image.new("RGB", (256, 256), "white")
                background.paste(rgba, mask=rgba.getchannel("A"))
                output = BytesIO()
                background.save(output, "JPEG", quality=88, optimize=True)
                return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode(
                    "ascii"
                )
    except (
        ValueError,
        binascii.Error,
        OSError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise InvalidInput(
            "La foto debe ser una imagen JPG, PNG o WebP válida (máximo 2 MB)."
        ) from exc
