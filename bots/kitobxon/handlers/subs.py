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
    # Record that user sent join request to this Zayafka channel
    # This marks it as "requested" so it won't show in subscription checks
    await subs.approve_zayafka(user.id, request.chat.id)

    # Note: Auto-approval is removed. Admin will manually approve join requests
    # in the Telegram channel. This ensures better control over who joins.
