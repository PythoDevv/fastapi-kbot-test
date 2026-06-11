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
NAME_Y_RATIO = 0.40           # vertical center of the name line
NAME_MAX_WIDTH_RATIO = 0.7    # name must fit within 70% of the width
NAME_MAX_FONT = 150
NAME_MIN_FONT = 60
NAME_FONT_STEP = 4
NAME_COLOR = (20, 20, 20)
QR_LINK = "https://t.me/Kitobxon_millatmiz"
QR_SIZE_RATIO = 0.07
QR_MARGIN_X_RATIO = 0.03
QR_MARGIN_BOTTOM_RATIO = 0.06
QR_BACKGROUND_PADDING_RATIO = 0.004


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


def _build_qr_image(qr_size: int):
    try:
        import qrcode
        from PIL import Image
    except ImportError:
        logger.warning("qrcode or Pillow not installed, skipping QR overlay")
        return None

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(QR_LINK)
    qr.make(fit=True)

    qr_image = qr.make_image(fill_color="black", back_color="white")
    if hasattr(qr_image, "get_image"):
        qr_image = qr_image.get_image()
    qr_image = qr_image.convert("RGB")
    return qr_image.resize((qr_size, qr_size), Image.Resampling.LANCZOS)


def _paste_qr_code(img) -> None:
    w, h = img.size
    qr_size = max(140, int(w * QR_SIZE_RATIO))
    qr_image = _build_qr_image(qr_size)
    if qr_image is None:
        return

    from PIL import Image

    padding = max(10, int(w * QR_BACKGROUND_PADDING_RATIO))
    background = Image.new(
        "RGB",
        (qr_size + padding * 2, qr_size + padding * 2),
        "white",
    )
    background.paste(qr_image, (padding, padding))

    x = int(w * QR_MARGIN_X_RATIO)
    y = h - background.height - int(h * QR_MARGIN_BOTTOM_RATIO)
    img.paste(background, (x, y))


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
        _paste_qr_code(img)

        output = io.BytesIO()
        img.save(output, format="JPEG", quality=90, optimize=True)
        output.seek(0)
        return output
    except Exception:
        logger.exception("Certificate generation failed")
        return None
