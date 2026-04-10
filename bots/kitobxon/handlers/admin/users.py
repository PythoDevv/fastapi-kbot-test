from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.keyboards import inline, reply
from bots.kitobxon.services import AdminService
from bots.kitobxon.states import AdminScoreStates

router = Router(name="admin_users")


async def _is_admin(session: AsyncSession, telegram_id: int) -> bool:
    from bots.kitobxon.repositories import UserRepository
    user = await UserRepository(session).get_by_telegram_id(telegram_id)
    return bool(user and user.is_admin)


@router.message(F.text == "👥 Foydalanuvchilar")
async def users_menu(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    await message.answer(
        "Foydalanuvchi ID sini yuboring (Telegram ID):",
        reply_markup=reply.cancel_only(),
    )


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
        new_score = int(message.text.strip())
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
    reason = message.text.strip() if message.text.strip() != "-" else None
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
