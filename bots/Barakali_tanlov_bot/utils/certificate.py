"""
Certificate generator using PIL.
Template: bots/Barakali_tanlov_bot/Barakali_tanlov_bot.jpg
Fonts: static/fonts/
"""
import io
import os
from pathlib import Path

from aiogram.types import BufferedInputFile
from core.logging import get_logger

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parents[3] / "static"
BOT_DIR = Path(__file__).resolve().parents[1]
CERT_TEMPLATE = str(BOT_DIR / "Barakali_tanlov_bot.jpg")
ALT_CERT_TEMPLATE = str(BASE_DIR / "certificates" / "template.png")
FONT_DIR = str(BASE_DIR / "fonts")
# The name line on the Barakali certificate is centered around y=437 in the
# 1280x906 original template.
NAME_Y_RATIO = 0.436
NAME_BASE_FONT_SIZE = 100
NAME_X_OFFSET = 0


def resolve_certificate_template_path() -> str | None:
    """Return the first available certificate template path."""
    for candidate in (CERT_TEMPLATE, ALT_CERT_TEMPLATE):
        if os.path.exists(candidate):
            return candidate
    return None


def build_certificate_input_file(buffer: io.BytesIO, filename: str = "certificate.png") -> BufferedInputFile:
    buffer.seek(0)
    return BufferedInputFile(buffer.read(), filename=filename)


def _get_optimal_font_size(text: str, max_width: int, base_size: int = 60) -> int:
    """Calculate optimal font size based on text length and available width"""
    try:
        from PIL import ImageFont
    except ImportError:
        return base_size
    
    name_len = len(text)
    # Dynamically reduce font size for longer names
    if name_len > 20:
        return max(32, base_size - (name_len - 15) * 2)
    elif name_len > 15:
        return base_size - 8
    elif name_len > 12:
        return base_size - 4
    return base_size


def _format_name_case(name: str) -> str:
    """Format name with proper case handling (capitalize first letter of each word)"""
    return " ".join(word.capitalize() for word in name.split())


def get_name_layout(full_name: str, img_w: int, img_h: int) -> tuple[int, int, int]:
    formatted_name = _format_name_case(full_name.strip())
    # Keep the name size proportional when a certificate template changes
    # resolution.  The base size was originally tuned for a 3508px-wide image.
    base_size = max(24, round(NAME_BASE_FONT_SIZE * img_w / 3508))
    font_size = _get_optimal_font_size(
        formatted_name,
        int(img_w * 0.45),
        base_size=base_size,
    )
    name_y = int(img_h * NAME_Y_RATIO)
    return font_size, name_y, NAME_X_OFFSET


def generate_certificate(
    full_name: str,
    score: int,
    total: int,
    font_name: str = "DejaVuSans-Bold.ttf",
    include_total: bool = True,
) -> io.BytesIO | None:
    """
    Generate a high-quality certificate PNG and return as BytesIO.

    Features:
    - Adaptive font sizing based on name length
    - Proper name formatting (title case)
    - High-quality output
    - Better text rendering with anti-aliasing
    - Optionally hide the total score for cleaner output

    Returns None if template is not found.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.error("Pillow not installed")
        return None

    template_path = resolve_certificate_template_path()
    if template_path is None:
        logger.warning(
            "Certificate template not found. Checked paths: %s, %s",
            CERT_TEMPLATE,
            ALT_CERT_TEMPLATE,
        )
        return None
    if template_path != CERT_TEMPLATE:
        logger.warning("Certificate template missing in static path, using fallback: %s", template_path)

    font_path = os.path.join(FONT_DIR, font_name)
    try:
        img = Image.open(template_path).convert("RGBA")
        draw = ImageDraw.Draw(img, "RGBA")

        img_w, img_h = img.size
        
        # Format name with proper case
        formatted_name = _format_name_case(full_name.strip())
        name_font_size, name_y, name_x_offset = get_name_layout(full_name, img_w, img_h)
        
        # Name font
        try:
            name_font = ImageFont.truetype(font_path, size=name_font_size)
        except (IOError, OSError):
            name_font = ImageFont.load_default()
            logger.warning("Could not load TrueType font, using default")

        # Center the name on the dedicated line in the template.
        bbox = draw.textbbox((0, 0), formatted_name, font=name_font)
        text_w = bbox[2] - bbox[0]
        name_x = (img_w - text_w) // 2 + name_x_offset

        # Make exceptionally long full names fit inside the name line.
        max_name_width = int(img_w * 0.45)
        while text_w > max_name_width and name_font_size > 24:
            name_font_size -= 1
            try:
                name_font = ImageFont.truetype(font_path, size=name_font_size)
            except (IOError, OSError):
                break
            bbox = draw.textbbox((0, 0), formatted_name, font=name_font)
            text_w = bbox[2] - bbox[0]
            name_x = (img_w - text_w) // 2 + name_x_offset

        # Draw name with shadow effect for better quality
        shadow_offset = 2
        draw.text(
            (name_x + shadow_offset, name_y + shadow_offset),
            formatted_name,
            font=name_font,
            fill=(200, 200, 200, 100),
        )
        # Main name text
        draw.text(
            (name_x, name_y),
            formatted_name,
            font=name_font,
            fill=(33, 33, 33, 255),
        )

        if include_total:
            # Score font
            try:
                score_font = ImageFont.truetype(font_path, size=40)
            except (IOError, OSError):
                score_font = ImageFont.load_default()

            score_text = f"{score}/{total}"
            score_bbox = draw.textbbox((0, 0), score_text, font=score_font)
            score_w = score_bbox[2] - score_bbox[0]
            score_x = (img_w - score_w) // 2
            score_y = int(img_h * 0.62)

            # Draw score with shadow effect
            draw.text(
                (score_x + shadow_offset, score_y + shadow_offset),
                score_text,
                font=score_font,
                fill=(200, 200, 200, 100),
            )
            # Main score text
            draw.text(
                (score_x, score_y),
                score_text,
                font=score_font,
                fill=(80, 80, 80, 255),
            )

        output = io.BytesIO()
        # Convert to RGB and save with high quality
        img_rgb = Image.new("RGB", img.size, (255, 255, 255))
        img_rgb.paste(img, mask=img.split()[3] if img.mode == "RGBA" else None)
        img_rgb.save(output, format="PNG", quality=95, optimize=False)
        output.seek(0)
        return output

    except Exception:
        logger.exception("Certificate generation failed")
        return None
