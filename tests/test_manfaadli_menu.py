from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bots.Manfaadli_konkurs_bot.cache import runtime_cache
from bots.Manfaadli_konkurs_bot.handlers.auth import handle_name_change
from bots.Manfaadli_konkurs_bot.keyboards import reply


def _keyboard_texts(markup) -> set[str]:
    return {
        button.text
        for row in markup.keyboard
        for button in row
    }


@pytest.mark.asyncio
async def test_name_change_rebuilds_menu_from_persisted_certificate_setting() -> None:
    runtime_cache.set_certificate_button_enabled(False)

    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = SimpleNamespace(
        show_certificate_button=True
    )
    session = AsyncMock()
    session.execute.return_value = query_result

    message = SimpleNamespace(
        text="Yangi Ism Familiya",
        from_user=SimpleNamespace(id=42),
        answer=AsyncMock(),
    )
    state = AsyncMock()

    with patch(
        "bots.Manfaadli_konkurs_bot.handlers.auth.AuthService.set_name",
        new=AsyncMock(),
    ):
        await handle_name_change(message, state, session)

    markup = message.answer.await_args.kwargs["reply_markup"]
    assert reply.CERTIFICATE_BUTTON_TEXT in _keyboard_texts(markup)

