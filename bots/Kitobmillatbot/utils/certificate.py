"""
Certificate generator.

Draws the participant's name onto the pre-designed certificate.jpg
(the empty gap between the "SERTIFIKAT" title and the body text).

Fast path:
- Base image is decoded once and cached in memory; each request only
  copies it, draws the name and re-encodes to JPEG.
- Fonts are cached per size.
- Output is JPEG (much faster + smaller than PNG for a 3508x2480 image).
"""
import io
import os
from functools import lru_cache
from pathlib import Path

from aiogram.types import BufferedInputFile
from core.logging import get_logger

logger = get_logger(__name__)

BOT_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = Path(__file__).resolve().parents[3] / "static"

# Pre-designed template that already contains all the static text.
CERT_TEMPLATE = str(BOT_DIR / "certificate.jpg")

# Bold font: bundled first (guaranteed in Docker), then common system paths.
FONT_CANDIDATES = (
    str(STATIC_DIR / "fonts" / "DejaVuSans-Bold.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)

# Name placement (ratios of full image size).
NAME_Y_RATIO = 0.345          # vertical center of the name line
NAME_MAX_WIDTH_RATIO = 0.7    # name must fit within 70% of the width
NAME_MAX_FONT = 150
NAME_MIN_FONT = 60
NAME_FONT_STEP = 4
NAME_COLOR = (20, 20, 20)


def build_certificate_input_file(buffer: io.BytesIO, filename: str = "sertifikat.jpg") -> BufferedInputFile:
    buffer.seek(0)
    return BufferedInputFile(buffer.read(), filename=filename)


def _format_name_case(name: str) -> str:
    """Capitalize the first letter of each word."""
    return " ".join(word.capitalize() for word in name.split())


@lru_cache(maxsize=1)
def _base_image():
    """Decode the template once and cache it. Returns None if missing."""
    try:
        from PIL import Image
    except ImportError:
        logger.error("Pillow not installed")
        return None
    if not os.path.exists(CERT_TEMPLATE):
        logger.warning("Certificate template not found: %s", CERT_TEMPLATE)
        return None
    return Image.open(CERT_TEMPLATE).convert("RGB")


@lru_cache(maxsize=16)
def _load_font(size: int):
    from PIL import ImageFont

    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    logger.warning("No TrueType font found, using PIL default")
    return ImageFont.load_default()


def _fit_font(draw, text: str, max_width: int):
    """Largest font (within bounds) that keeps the text under max_width."""
    size = NAME_MAX_FONT
    while size > NAME_MIN_FONT:
        font = _load_font(size)
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= NAME_FONT_STEP
    return _load_font(NAME_MIN_FONT)


def generate_certificate(
    full_name: str,
    score: int = 0,
    total: int = 0,
    font_name: str = "DejaVuSans-Bold.ttf",
    include_total: bool = False,
) -> io.BytesIO | None:
    """
    Render the name onto certificate.jpg and return JPEG bytes.

    score / total / include_total are kept for backwards compatibility
    but ignored: this template already carries all the static text and
    only needs the participant's name.

    Returns None if the template or Pillow is unavailable.
    """
    base = _base_image()
    if base is None:
        return None

    try:
        from PIL import ImageDraw

        img = base.copy()
        draw = ImageDraw.Draw(img)
        w, h = img.size

        name = _format_name_case(full_name.strip())
        font = _fit_font(draw, name, int(w * NAME_MAX_WIDTH_RATIO))

        bbox = draw.textbbox((0, 0), name, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (w - text_w) // 2 - bbox[0]
        y = int(h * NAME_Y_RATIO) - text_h // 2 - bbox[1]

        draw.text((x, y), name, font=font, fill=NAME_COLOR)

        output = io.BytesIO()
        img.save(output, format="JPEG", quality=90, optimize=True)
        output.seek(0)
        return output
    except Exception:
        logger.exception("Certificate generation failed")
        return None
