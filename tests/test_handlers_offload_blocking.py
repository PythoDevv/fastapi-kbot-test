"""Regression: heavy synchronous work (PIL certificate render, openpyxl excel
build/parse) must be offloaded to a worker thread via ``asyncio.to_thread`` so it
never blocks the shared event loop.

In webhook mode all bots run in one process / one event loop, so a single
blocking call freezes every bot for every user (the "qotish / press twice"
symptom). These call sites must stay offloaded: the blocking function may only
appear as an argument to ``asyncio.to_thread(...)`` — never invoked directly as
``func(...)``.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BOTS = ["kitobxon", "Kitobmillatbot", "Millatchiroqlaribot"]

# (relative handler path, blocking function name that must be offloaded)
BLOCKING_CALLS = [
    ("handlers/results.py", "generate_certificate"),
    ("handlers/admin/export.py", "export_users_to_excel"),
    ("handlers/admin/export.py", "export_referred_users_to_excel"),
    ("handlers/admin/export.py", "export_answers_to_excel"),
    ("handlers/admin/export.py", "export_test_results_summary_to_excel"),
    ("handlers/admin/export.py", "export_top_answers_to_excel"),
    ("handlers/admin/questions.py", "export_questions_to_excel"),
    ("handlers/admin/questions.py", "import_questions_from_excel"),
]


@pytest.mark.parametrize("bot", BOTS)
@pytest.mark.parametrize("relpath,func", BLOCKING_CALLS)
def test_blocking_call_is_offloaded(bot, relpath, func):
    src = (ROOT / "bots" / bot / relpath).read_text(encoding="utf-8")

    # Must actually be offloaded: appear as a to_thread argument.
    offloaded = re.search(rf"to_thread\(\s*{func}\b", src)
    assert offloaded, (
        f"{bot}/{relpath}: {func} is not offloaded via asyncio.to_thread"
    )

    # Must NOT be invoked directly as func(...) — that would block the loop.
    direct = re.search(rf"\b{func}\(", src)
    assert direct is None, (
        f"{bot}/{relpath}: {func}(...) is called directly at offset "
        f"{direct.start() if direct else -1}; it will freeze the event loop"
    )
