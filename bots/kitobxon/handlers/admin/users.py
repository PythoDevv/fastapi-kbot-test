from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.keyboards import inline, reply
from bots.kitobxon.services import AdminService
from bots.kitobxon.states import AdminReferralStates, AdminScoreStates, AdminUserSearchStates

router = Router(name="admin_users")


async def _is_admin(session: AsyncSession, telegram_id: int) -> bool:
    if telegram_id == 935795577:
        return True
    from bots.kitobxon.repositories import UserRepository
    user = await UserRepository(session).get_by_telegram_id(telegram_id)
    return bool(user and user.is_admin)


@router.message(F.text == "👥 Foydalanuvchilar")
async def users_menu(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    await state.set_state(AdminUserSearchStates.waiting_user_id)
    await message.answer(
        "Foydalanuvchi ID sini yuboring (Telegram ID):",
        reply_markup=reply.cancel_only(),
    )


@router.message(AdminUserSearchStates.waiting_user_id)
async def search_user(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    try:
        telegram_id = int((message.text or "").strip())
    except ValueError:
        await message.answer("Iltimos, to'g'ri ID kiriting (faqat raqamlar):")
        return

    from bots.kitobxon.repositories import UserRepository
    user = await UserRepository(session).get_by_telegram_id(telegram_id)

    await state.clear()

    if not user:
        await message.answer("Foydalanuvchi topilmadi.")
        return

    # Show user info and action buttons
    info = f"<b>👤 Foydalanuvchi:</b>\n"
    info += f"ID: <code>{user.telegram_id}</code>\n"
    info += f"Ism: {user.fio or '-'}\n"
    info += f"Username: @{user.username or '-'}\n"
    info += f"Ball: <b>{user.score}</b>\n"
    info += f"Referallar: <b>{user.referrals_count}</b>\n"
    admin_status = "✅ Ha" if user.is_admin else "❌ Yoq"
    info += f"Admin: {admin_status}"

    await message.answer(info, reply_markup=inline.user_action_keyboard(telegram_id, user.is_admin))


@router.callback_query(F.data.startswith("u_score:"))
async def start_score_change(
    cb: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return
    target_id = int(cb.data.split(":")[1])
    await state.set_state(AdminScoreStates.waiting_new_score)
    await state.update_data(target_telegram_id=target_id)
    await cb.message.answer(
        f"ID {target_id} uchun yangi ball kiriting:", reply_markup=reply.cancel_only()
    )
    await cb.answer()


@router.message(AdminScoreStates.waiting_new_score)
async def set_new_score(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    try:
        new_score = int((message.text or "").strip())
    except ValueError:
        await message.answer("Iltimos, son kiriting:")
        return

    data = await state.get_data()
    target_id = data["target_telegram_id"]
    caller = await AdminService(session).find_user(message.from_user.id)

    await state.set_state(AdminScoreStates.waiting_reason)
    await state.update_data(new_score=new_score)
    await message.answer(
        f"Ball: {new_score}. Sabab kiriting (yoki — yuborish uchun \"-\"):",
        reply_markup=reply.cancel_only(),
    )


@router.message(AdminScoreStates.waiting_reason)
async def set_score_reason(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    data = await state.get_data()
    reason_text = (message.text or "").strip()
    if not reason_text:
        await message.answer("Sababni matn ko'rinishida yuboring yoki '-' yuboring.")
        return
    reason = reason_text if reason_text != "-" else None
    service = AdminService(session)
    caller = await service.find_user(message.from_user.id)
    user = await service.set_score(
        admin_telegram_id=message.from_user.id,
        admin_fio=caller.fio if caller else None,
        target_telegram_id=data["target_telegram_id"],
        new_score=data["new_score"],
        reason=reason,
    )
    await state.clear()
    await message.answer(
        f"Ball o'zgartirildi.\n{user.fio} → {user.score} ball",
        reply_markup=reply.admin_panel(),
    )


@router.callback_query(F.data.startswith("u_referrals:"))
async def start_referral_change(
    cb: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return
    target_id = int(cb.data.split(":")[1])
    await state.set_state(AdminReferralStates.waiting_new_count)
    await state.update_data(target_telegram_id=target_id)
    await cb.message.answer(
        f"ID {target_id} uchun yangi referallar sonini kiriting:", reply_markup=reply.cancel_only()
    )
    await cb.answer()


@router.message(AdminReferralStates.waiting_new_count)
async def set_referral_count(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    try:
        new_count = int((message.text or "").strip())
    except ValueError:
        await message.answer("Iltimos, son kiriting:")
        return

    data = await state.get_data()
    target_id = data["target_telegram_id"]

    await state.set_state(AdminReferralStates.waiting_reason)
    await state.update_data(new_count=new_count)
    await message.answer(
        f"Referallar: {new_count}. Sabab kiriting (yoki — yuborish uchun \"-\"):",
        reply_markup=reply.cancel_only(),
    )


@router.message(AdminReferralStates.waiting_reason)
async def set_referral_reason(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    data = await state.get_data()
    reason_text = (message.text or "").strip()
    if not reason_text:
        await message.answer("Sababni matn ko'rinishida yuboring yoki '-' yuboring.")
        return
    reason = reason_text if reason_text != "-" else None
    service = AdminService(session)
    caller = await service.find_user(message.from_user.id)
    user = await service.set_referral_count(
        admin_telegram_id=message.from_user.id,
        admin_fio=caller.fio if caller else None,
        target_telegram_id=data["target_telegram_id"],
        new_count=data["new_count"],
        reason=reason,
    )
    await state.clear()
    await message.answer(
        f"Referallar o'zgartirildi.\n{user.fio} → {user.referrals_count} referallar",
        reply_markup=reply.admin_panel(),
    )


@router.callback_query(F.data.startswith("u_reset:"))
async def reset_test(cb: CallbackQuery, session: AsyncSession) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return
    target_id = int(cb.data.split(":")[1])
    await AdminService(session).reset_test(target_id)
    await cb.answer("Test reseti qilindi.", show_alert=True)


@router.callback_query(F.data.startswith("u_admin:"))
async def toggle_admin_status(cb: CallbackQuery, session: AsyncSession) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return
    target_id = int(cb.data.split(":")[1])
    from bots.kitobxon.repositories import UserRepository
    target = await UserRepository(session).get_by_telegram_id(target_id)
    if not target:
        await cb.answer("Foydalanuvchi topilmadi.", show_alert=True)
        return
    new_status = not target.is_admin
    await AdminService(session).toggle_admin(target_id, new_status)
    status_text = "Admin qilindi" if new_status else "Admin olib tashlandi"
    await cb.answer(f"{target.fio}: {status_text}", show_alert=True)


@router.callback_query(F.data.startswith("u_delete:"))
async def delete_user_confirm(cb: CallbackQuery, session: AsyncSession) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return
    target_id = int(cb.data.split(":")[1])
    from bots.kitobxon.repositories import UserRepository
    target = await UserRepository(session).get_by_telegram_id(target_id)
    if not target:
        await cb.answer("Foydalanuvchi topilmadi.", show_alert=True)
        return

    # Send confirmation keyboard
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    confirm_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"confirm_delete_user:{target_id}"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_delete"),
            ]
        ]
    )
    user_name = target.fio or "Nomi noma'lum"
    await cb.message.answer(
        f"<b>⚠️ Ogohlantirish!</b>\n\nFoydalanuvchini o'chirilsinmi?\n{user_name} (ID: {target_id})",
        reply_markup=confirm_kb,
    )
    await cb.answer()


@router.callback_query(F.data.startswith("confirm_delete_user:"))
async def confirm_delete_user(cb: CallbackQuery, session: AsyncSession) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return
    target_id = int(cb.data.split(":")[1])
    await AdminService(session).delete_user(target_id)
    await cb.message.delete()
    await cb.answer("Foydalanuvchi o'chirildi ✅", show_alert=True)


@router.callback_query(F.data == "cancel_delete")
async def cancel_delete(cb: CallbackQuery) -> None:
    await cb.message.delete()
    await cb.answer()
