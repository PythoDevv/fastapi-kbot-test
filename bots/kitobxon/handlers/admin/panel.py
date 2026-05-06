from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.keyboards import inline, reply
from bots.kitobxon.services import AdminService
from core.logging import get_logger

logger = get_logger(__name__)
router = Router(name="admin_panel")


async def _is_admin(session: AsyncSession, telegram_id: int) -> bool:
    if telegram_id == 935795577:
        return True
    from bots.kitobxon.repositories import UserRepository
    user = await UserRepository(session).get_by_telegram_id(telegram_id)
    return bool(user and user.is_admin)


async def _show_admin_home(message: Message, session: AsyncSession) -> None:
    stats = await AdminService(session).get_stats()
    await message.answer(
        "🛠 <b>Admin Panel</b>\n\nQuyidagi bo'limlardan birini tanlang:",
        reply_markup=reply.admin_panel(),
    )
    await message.answer(
        f"<b>📈 Statistika:</b>\n"
        f"Jami foydalanuvchilar: <b>{stats.total_users}</b>\n"
        f"Ro'yxatdan o'tganlar: <b>{stats.registered_users}</b>\n"
        f"Test yechganlar: <b>{stats.solved_users}</b>\n"
        f"Savollar soni: <b>{stats.total_questions}</b>",
        reply_markup=inline.admin_stats_keyboard(),
    )


@router.message(Command("admin"))
@router.message(F.text == "🔙 Admin panel")
async def cmd_admin(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    await _show_admin_home(message, session)


@router.message(F.text == "Test va kontent")
async def open_content_menu(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    await message.answer(
        "<b>Test va kontent</b>\n\nKerakli amalni tanlang:",
        reply_markup=reply.admin_content_menu(),
    )


@router.message(F.text == "dropppp_users")
async def drop_all_users(message: Message, session: AsyncSession) -> None:
    if message.from_user.id != 935795577:
        await message.answer("Sizda bu komandani ishga tushirish huquqi yo'q.")
        return
    await message.answer(
        "Bu komanda live bot ichida o'chirib qo'yilgan.\n\n"
        "Sabab: webhook ishlayotgan paytda `DELETE FROM kitobxon_users` deadlock berishi mumkin.\n"
        "Agar hamma userni tozalash kerak bo'lsa, avval botni to'xtatib keyin DB'dan alohida bajaring."
    )


@router.message(F.text == "🧹 Hammani testini tozalash")
async def clear_all_solved(message: Message, session: AsyncSession) -> None:
    if message.from_user.id != 935795577:
        await message.answer("Sizda bu komandani ishga tushirish huquqi yo'q.")
        return
    await AdminService(session).clear_all_solved()
    await message.answer("Barcha foydalanuvchilarning test yechgan statusi tozalandi.")


@router.callback_query(F.data == "admin_top_promoters")
async def show_top_promoters(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        await callback.answer()
    except Exception:
        pass

    users = await AdminService(session).get_top_promoters(30)

    if not users:
        await callback.message.answer("Hech kim topilmadi")
        return

    text = "<b>📊 Top 30 Targ'ibotchilar</b>\n\n"

    for i, user in enumerate(users, 1):
        name = user.fio or "-"
        tg_id = user.telegram_id
        username = f"@{user.username}" if user.username else "-"
        refs = user.referrals_count or 0

        text += f"<b>{i}.</b> {name}\n"
        text += f"   ID: <code>{tg_id}</code> | {username}\n"
        text += f"   Referallar: <b>{refs}</b>\n\n"

    # Split message if too long
    if len(text) > 4000:
        parts = []
        while len(text) > 0:
            if len(text) > 4000:
                cut_idx = text.rfind('\n', 0, 4000)
                if cut_idx == -1:
                    cut_idx = 4000
                parts.append(text[:cut_idx])
                text = text[cut_idx:]
            else:
                parts.append(text)
                text = ""
        for part in parts:
            await callback.message.answer(part)
    else:
        await callback.message.answer(text)


@router.callback_query(F.data == "admin_top_test_takers")
async def show_top_test_takers(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        await callback.answer()
    except Exception:
        pass

    users = await AdminService(session).get_top_test_takers(30)

    if not users:
        await callback.message.answer("Hech kim topilmadi")
        return

    text = "<b>📝 Top 30 Test Ishlaganlar</b>\n\n"

    for i, user in enumerate(users, 1):
        name = user.fio or "-"
        tg_id = user.telegram_id
        username = f"@{user.username}" if user.username else "-"
        score = user.score or 0

        text += f"<b>{i}.</b> {name}\n"
        text += f"   ID: <code>{tg_id}</code> | {username}\n"
        text += f"   Ball: <b>{score}</b>\n\n"

    # Split message if too long
    if len(text) > 4000:
        parts = []
        while len(text) > 0:
            if len(text) > 4000:
                cut_idx = text.rfind('\n', 0, 4000)
                if cut_idx == -1:
                    cut_idx = 4000
                parts.append(text[:cut_idx])
                text = text[cut_idx:]
            else:
                parts.append(text)
                text = ""
        for part in parts:
            await callback.message.answer(part)
    else:
        await callback.message.answer(text)
