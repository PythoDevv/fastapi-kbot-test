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


if __name__ == "__main__":
    unittest.main()
