from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.Kitobmillatbot.keyboards import reply
from bots.Kitobmillatbot.repositories import UserRepository
from bots.Kitobmillatbot.services import AdminService
from bots.Kitobmillatbot.states import AdminAdminStates

router = Router(name="admin_admins")


async def _is_admin(session: AsyncSession, telegram_id: int) -> bool:
    if telegram_id == 935795577:
        return True
    user = await UserRepository(session).get_by_telegram_id(telegram_id)
    return bool(user and user.is_admin)


async def show_admin_list(message_or_cb, session: AsyncSession, is_callback: bool = False):
    """Show list of all admins"""
    repo = UserRepository(session)
    all_users = await repo.list()
    admins = [u for u in all_users if u.is_admin]

    text = "<b>👥 Admin ro'yxati:</b>\n\n"

    buttons = []
    for admin in admins:
        admin_name = admin.fio or "Nomi noma'lum"
        text += f"• {admin_name} (ID: <code>{admin.telegram_id}</code>)\n"
        buttons.append(
            [InlineKeyboardButton(
                text=f"🚫 {admin.fio or admin.telegram_id}",
                callback_data=f"demote_admin:{admin.telegram_id}",
            )]
        )

    buttons.append(
        [InlineKeyboardButton(text="➕ Yangi admin qo'shish", callback_data="add_admin_start")]
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    if is_callback:
        await message_or_cb.message.edit_text(text, reply_markup=keyboard)
    else:
        await message_or_cb.answer(text, reply_markup=keyboard)


@router.message(F.text == reply.ADMIN_BUTTON_ADMINS)
async def show_admins(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    await show_admin_list(message, session)


@router.callback_query(F.data == "add_admin_start")
async def start_add_admin(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminAdminStates.waiting_id)
    await cb.message.answer(
        "Yangi admin qilish uchun Telegram ID sini yuboring:",
        reply_markup=reply.cancel_only(),
    )
    await cb.answer()


@router.message(AdminAdminStates.waiting_id)
async def add_admin_confirm(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    try:
        telegram_id = int((message.text or "").strip())
    except ValueError:
        await message.answer("Iltimos, to'g'ri ID kiriting (faqat raqamlar):")
        return

    repo = UserRepository(session)
    user = await repo.get_by_telegram_id(telegram_id)

    if not user:
        await message.answer("Foydalanuvchi topilmadi.")
        await state.clear()
        return

    if user.is_admin:
        await message.answer("Bu foydalanuvchi allaqachon admin.")
        await state.clear()
        return

    # Promote to admin
    await AdminService(session).toggle_admin(telegram_id, True)
    await state.clear()
    await message.answer(
        f"✅ {user.fio or 'Foydalanuvchi'} admin qilindi!",
        reply_markup=reply.admin_panel(),
    )


@router.callback_query(F.data.startswith("demote_admin:"))
async def demote_admin(cb: CallbackQuery, session: AsyncSession) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return

    target_id = int(cb.data.split(":")[1])

    # Don't allow demoting yourself
    if target_id == cb.from_user.id:
        await cb.answer("O'zingizni admin olib tashlay olmaysiz.", show_alert=True)
        return

    repo = UserRepository(session)
    user = await repo.get_by_telegram_id(target_id)

    if not user:
        await cb.answer("Foydalanuvchi topilmadi.", show_alert=True)
        return

    await AdminService(session).toggle_admin(target_id, False)
    await cb.answer(f"✅ {user.fio} admindan olib tashlandi.", show_alert=True)

    # Refresh admin list
    await show_admin_list(cb, session, is_callback=True)
