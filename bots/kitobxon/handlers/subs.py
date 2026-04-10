from aiogram import Bot, Router
from aiogram.types import ChatJoinRequest
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.repositories import UserRepository
from bots.kitobxon.services import SubsService
from core.logging import get_logger

logger = get_logger(__name__)
router = Router(name="subs")


@router.chat_join_request()
async def handle_join_request(
    request: ChatJoinRequest, bot: Bot, session: AsyncSession
) -> None:
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(request.from_user.id)
    if not user:
        return

    subs = SubsService(session)
    await subs.approve_zayafka(user.id, request.chat.id)

    try:
        await bot.approve_chat_join_request(
            chat_id=request.chat.id, user_id=request.from_user.id
        )
    except Exception as exc:
        logger.warning("Failed to approve join request: %s", exc)
