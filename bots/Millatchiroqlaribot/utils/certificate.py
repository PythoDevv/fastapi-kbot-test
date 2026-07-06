"""
Certificate generator using PIL.
Draws the participant's name centered on the divider line of the
pre-designed certificate.jpg, using an elegant serif font.
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

# Pre-designed template (already carries all the static text).
CERT_TEMPLATE = str(BOT_DIR / "certificate.jpg")

# Elegant serif first, then bundled bold sans, then common system paths.
FONT_CANDIDATES = (
    str(STATIC_DIR / "fonts" / "NotoSerifDisplay-Bold.ttf"),
    "/usr/share/fonts/truetype/noto/NotoSerifDisplay-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    str(STATIC_DIR / "fonts" / "DejaVuSans-Bold.ttf"),
)

# Name placement (ratios of full image size).
NAME_Y_RATIO = 0.388          # the divider line the name rests on
NAME_BASELINE_GAP = 12        # px above the line so text sits ON it
NAME_MAX_WIDTH_RATIO = 0.72   # name must fit within this fraction of width
NAME_MAX_FONT = 60            # capped so ascenders clear "Ushbu sertifikat"
NAME_MIN_FONT = 34
NAME_FONT_STEP = 3
NAME_COLOR = (33, 33, 33)


def build_certificate_input_file(buffer: io.BytesIO, filename: str = "sertifikat.png") -> BufferedInputFile:
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


@lru_cache(maxsize=32)
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
    """Largest font (within bounds) that keeps text under max_width."""
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
    font_name: str = "",
    include_total: bool = False,
) -> io.BytesIO | None:
    """
    Render the name onto certificate.jpg, resting on the divider line.

    score / total / include_total are kept for backwards compatibility
    but ignored — the template already carries all static text.

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

        cx = w // 2
        baseline_y = int(h * NAME_Y_RATIO) - NAME_BASELINE_GAP
        # anchor="ms": x is horizontal midpoint, y is the text baseline,
        # so the name sits directly on the line.
        draw.text((cx, baseline_y), name, font=font, fill=NAME_COLOR, anchor="ms")

        output = io.BytesIO()
        img.save(output, format="PNG", optimize=False)
        output.seek(0)
        return output
    except Exception:
        logger.exception("Certificate generation failed")
        return None
