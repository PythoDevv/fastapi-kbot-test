from aiogram import Bot, Router
from aiogram.types import ChatJoinRequest
from sqlalchemy.ext.asyncio import AsyncSession

from bots.Kitobmillatbot.services import AuthService, SubsService
from core.logging import get_logger

logger = get_logger(__name__)
router = Router(name="subs")


@router.chat_join_request()
async def handle_join_request(
    request: ChatJoinRequest, bot: Bot, session: AsyncSession
) -> None:
    auth = AuthService(session)
    result = await auth.touch_user(
        telegram_id=request.from_user.id,
        username=request.from_user.username,
        first_name=request.from_user.first_name,
    )

    subs = SubsService(session)
    # Record that user sent join request so closed-channel checks
    # do not ask for the same request again.
    await subs.mark_zayafka_requested(result.user.id, request.chat.id)

    # Note: Auto-approval is removed. Admin will manually approve join requests
    # in the Telegram channel. This ensures better control over who joins.
