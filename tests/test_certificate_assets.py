import importlib
import logging
from pathlib import Path
import sys
import types
import unittest


ROOT_DIR = Path(__file__).resolve().parents[1]


def _stub_core_logging() -> None:
    module = types.ModuleType("core.logging")
    module.get_logger = logging.getLogger
    sys.modules["core.logging"] = module


def _import_certificate_module(module_name: str):
    _stub_core_logging()
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


class CertificateAssetResolutionTests(unittest.TestCase):
    def test_kitobxon_uses_local_template_when_primary_path_is_missing(self) -> None:
        module = _import_certificate_module("bots.kitobxon.utils.certificate")
        module.CERT_TEMPLATE = str(ROOT_DIR / "static" / "certificates" / "missing-template.png")
        module.ALT_CERT_TEMPLATE = str(ROOT_DIR / "bots" / "kitobxon" / "certificate.png")

        self.assertEqual(module.resolve_certificate_template_path(), module.ALT_CERT_TEMPLATE)

    def test_kitobmillatbot_uses_local_template_when_primary_path_is_missing(self) -> None:
        module = _import_certificate_module("bots.Kitobmillatbot.utils.certificate")
        module.CERT_TEMPLATE = str(ROOT_DIR / "static" / "certificates" / "missing-template.png")
        module.ALT_CERT_TEMPLATE = str(ROOT_DIR / "bots" / "Kitobmillatbot" / "certificate.png")

        self.assertEqual(module.resolve_certificate_template_path(), module.ALT_CERT_TEMPLATE)

    def test_kitobxon_builds_buffered_input_file_for_telegram(self) -> None:
        module = _import_certificate_module("bots.kitobxon.utils.certificate")
        payload = module.build_certificate_input_file(module.io.BytesIO(b"abc"))

        self.assertEqual(payload.filename, "certificate.png")

    def test_kitobmillatbot_builds_buffered_input_file_for_telegram(self) -> None:
        module = _import_certificate_module("bots.Kitobmillatbot.utils.certificate")
        payload = module.build_certificate_input_file(module.io.BytesIO(b"abc"))

        self.assertEqual(payload.filename, "certificate.png")

    def test_kitobxon_name_layout_moves_up_and_gets_bigger(self) -> None:
        module = _import_certificate_module("bots.kitobxon.utils.certificate")
        font_size, name_y, name_x_offset = module.get_name_layout("Ilyos", 3508, 2480)

        self.assertEqual(font_size, 100)
        self.assertEqual(name_y, int(2480 * 0.44))
        self.assertEqual(name_x_offset, -100)

    def test_kitobmillatbot_name_layout_moves_up_and_gets_bigger(self) -> None:
        module = _import_certificate_module("bots.Kitobmillatbot.utils.certificate")
        font_size, name_y, name_x_offset = module.get_name_layout("Ilyos", 3508, 2480)

        self.assertEqual(font_size, 100)
        self.assertEqual(name_y, int(2480 * 0.44))
        self.assertEqual(name_x_offset, -100)

    def test_kitobxonmillattbot_name_is_drawn_above_the_line(self) -> None:
        module = _import_certificate_module("bots.Kitobxonmillattbot.utils.certificate")
        line_y = 1210
        text_bbox = (0, 17, 816, 114)

        draw_y = module.get_name_draw_y(line_y, text_bbox)

        self.assertLess(draw_y + text_bbox[3], line_y)


if __name__ == "__main__":
    unittest.main()
