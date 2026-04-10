"""
Certificate generator using PIL.
Template: static/certificates/template.png
Fonts: static/fonts/
"""
import io
import os

from core.logging import get_logger

logger = get_logger(__name__)

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "static")
CERT_TEMPLATE = os.path.join(BASE_DIR, "certificates", "template.png")
FONT_DIR = os.path.join(BASE_DIR, "fonts")


def generate_certificate(
    full_name: str,
    score: int,
    total: int,
    font_name: str = "DejaVuSans.ttf",
) -> io.BytesIO | None:
    """
    Generate a certificate PNG and return as BytesIO.
    Returns None if template is not found.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.error("Pillow not installed")
        return None

    if not os.path.exists(CERT_TEMPLATE):
        logger.warning("Certificate template not found: %s", CERT_TEMPLATE)
        return None

    font_path = os.path.join(FONT_DIR, font_name)
    try:
        img = Image.open(CERT_TEMPLATE).convert("RGBA")
        draw = ImageDraw.Draw(img)

        # Name
        try:
            name_font = ImageFont.truetype(font_path, size=48)
        except (IOError, OSError):
            name_font = ImageFont.load_default()

        img_w, img_h = img.size
        _, _, text_w, text_h = draw.textbbox((0, 0), full_name, font=name_font)
        name_x = (img_w - text_w) // 2
        name_y = int(img_h * 0.52)
        draw.text((name_x, name_y), full_name, font=name_font, fill=(33, 33, 33))

        # Score
        try:
            score_font = ImageFont.truetype(font_path, size=32)
        except (IOError, OSError):
            score_font = ImageFont.load_default()

        score_text = f"{score}/{total}"
        _, _, sw, _ = draw.textbbox((0, 0), score_text, font=score_font)
        draw.text(
            ((img_w - sw) // 2, int(img_h * 0.63)),
            score_text,
            font=score_font,
            fill=(80, 80, 80),
        )

        output = io.BytesIO()
        img.convert("RGB").save(output, format="PNG", optimize=True)
        output.seek(0)
        return output

    except Exception:
        logger.exception("Certificate generation failed")
        return None
