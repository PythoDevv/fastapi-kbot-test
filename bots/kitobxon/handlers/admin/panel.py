from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.keyboards import reply
from bots.kitobxon.services import AdminService
from core.logging import get_logger

logger = get_logger(__name__)
router = Router(name="admin_panel")


async def _is_admin(session: AsyncSession, telegram_id: int) -> bool:
    from bots.kitobxon.repositories import UserRepository
    user = await UserRepository(session).get_by_telegram_id(telegram_id)
    return bool(user and user.is_admin)


@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    await message.answer("Admin panel:", reply_markup=reply.admin_panel())


@router.message(F.text == "📊 Statistika")
async def show_stats(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    stats = await AdminService(session).get_stats()
    await message.answer(
        f"<b>📊 Statistika</b>\n\n"
        f"Jami foydalanuvchilar: <b>{stats.total_users}</b>\n"
        f"Ro'yxatdan o'tganlar: <b>{stats.registered_users}</b>\n"
        f"Test yechganlar: <b>{stats.solved_users}</b>\n"
        f"Savollar soni: <b>{stats.total_questions}</b>"
    )
