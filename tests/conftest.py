"""Test-suite bootstrap.

`core.config` builds its Settings at import time, so any test that reaches the
service or handler layer needs the required variables present. Real values from
the environment (or a local .env) always win — these are only fallbacks so the
suite runs on a bare checkout.
"""

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

_TEST_ENV_DEFAULTS = {
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
    "BASE_WEBHOOK_URL": "https://example.invalid",
    "WEBHOOK_SECRET": "test-webhook-secret",
    "KITOBXON_BOT_TOKEN": "0:test-token",
}

for key, value in _TEST_ENV_DEFAULTS.items():
    os.environ.setdefault(key, value)
