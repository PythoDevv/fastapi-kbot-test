import io

from aiogram import F, Router
from aiogram.types import BufferedInputFile, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.repositories import UserRepository
from bots.kitobxon.utils.excel import export_users_to_excel

router = Router(name="admin_export")


async def _is_admin(session: AsyncSession, telegram_id: int) -> bool:
    user = await UserRepository(session).get_by_telegram_id(telegram_id)
    return bool(user and user.is_admin)


@router.message(F.text == "📥 Export Excel")
async def export_users(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    from bots.kitobxon.repositories import UserRepository
    users = list(
        (await session.execute(
            __import__("sqlalchemy", fromlist=["select"]).select(
                __import__(
                    "bots.kitobxon.models", fromlist=["User"]
                ).User
            ).where(
                __import__(
                    "bots.kitobxon.models", fromlist=["User"]
                ).User.is_registered.is_(True)
            ).order_by(
                __import__(
                    "bots.kitobxon.models", fromlist=["User"]
                ).User.id
            )
        )).scalars().all()
    )
    buf = export_users_to_excel(users)
    await message.answer_document(
        document=BufferedInputFile(buf.read(), filename="users.xlsx"),
        caption=f"Jami: {len(users)} foydalanuvchi",
    )
