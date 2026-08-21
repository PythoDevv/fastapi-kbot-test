import io
import unittest

from PIL import Image

from bots.Manfaadli_konkurs_bot.utils.certificate import (
    build_certificate_input_file,
    generate_certificate,
)


TEMPLATE_PATH = "bots/Manfaadli_konkurs_bot/manfaatli.jpg"


def _dark_pixel_count(image: Image.Image, box: tuple[int, int, int, int]) -> int:
    return sum(
        1
        for pixel in image.crop(box).convert("RGB").getdata()
        if max(pixel) < 140
    )


class ManfaadliCertificateTests(unittest.TestCase):
    def test_name_is_rendered_above_the_line(self) -> None:
        template = Image.open(TEMPLATE_PATH).convert("RGB")
        generated = Image.open(
            io.BytesIO(generate_certificate("Karshiboev Ilyos", 8, 10).getvalue())
        ).convert("RGB")

        # The area above the line is blank in manfaatli.jpg. A generated name
        # must create visible dark text there.
        self.assertGreater(
            _dark_pixel_count(generated, (180, 545, 800, 607))
            - _dark_pixel_count(template, (180, 545, 800, 607)),
            250,
        )

    def test_author_text_below_the_line_is_preserved(self) -> None:
        template = Image.open(TEMPLATE_PATH).convert("RGB")
        generated = Image.open(
            io.BytesIO(generate_certificate("Karshiboev Ilyos", 8, 10).getvalue())
        ).convert("RGB")

        # This crop contains the source's "To‘g‘ay Murodning" author line.
        template_count = _dark_pixel_count(template, (250, 610, 700, 655))
        generated_count = _dark_pixel_count(generated, (250, 610, 700, 655))
        self.assertGreater(generated_count, int(template_count * 0.7))
        self.assertLess(generated_count, int(template_count * 1.5))

    def test_each_certificate_request_gets_user_specific_content_and_file_name(self) -> None:
        first = generate_certificate("Karshiboev Ilyos", 8, 10).getvalue()
        second = generate_certificate("Ali Valiyev", 8, 10).getvalue()

        self.assertNotEqual(first, second)

        first_file = build_certificate_input_file(io.BytesIO(first))
        second_file = build_certificate_input_file(io.BytesIO(second))
        self.assertNotEqual(first_file.filename, second_file.filename)


if __name__ == "__main__":
    unittest.main()
