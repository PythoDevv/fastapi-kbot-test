from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.Kitobmillatbot.config import QuizType
from bots.Kitobmillatbot.keyboards import inline, reply
from bots.Kitobmillatbot.services import AdminService

router = Router(name="admin_settings")


async def _is_admin(session: AsyncSession, telegram_id: int) -> bool:
    if telegram_id == 935795577:
        return True
    from bots.Kitobmillatbot.repositories import UserRepository
    user = await UserRepository(session).get_by_telegram_id(telegram_id)
    return bool(user and user.is_admin)


def _require_phone_enabled(settings_obj) -> bool:
    return bool(
        getattr(
            settings_obj,
            "require_phone_number",
            getattr(settings_obj, "require_phone", False),
        )
    )


def _format_settings_text(settings_obj) -> str:
    status = "🟢 Faol" if settings_obj.active and not settings_obj.waiting and not settings_obj.finished else (
        "🟡 Kutmoqda" if settings_obj.waiting else "🔴 Yakunlangan"
    )
    phone_status = "✅ Talab" if _require_phone_enabled(settings_obj) else "❌ Ixtiyoriy"
    return (
        f"<b>⚙️ Test sozlamalari</b>\n\n"
        f"Status: {status}\n"
        f"Tur: {settings_obj.quiz_type.value.upper()}\n"
        f"Savollar: {settings_obj.questions_per_test}\n"
        f"O'tish bali: {settings_obj.limit_score}\n"
        f"Vaqt: {settings_obj.time_limit_seconds}s\n"
        f"Telefon: {phone_status}"
    )


@router.message(F.text == "⚙️ Test sozlamalari")
async def show_settings(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    s = await AdminService(session).get_settings()
    await message.answer(
        _format_settings_text(s),
        reply_markup=inline.quiz_settings_full_keyboard(
            s.active,
            s.waiting,
            s.finished,
            _require_phone_enabled(s),
            s.quiz_type.value,
        ),
    )


@router.callback_query(F.data == "qs_toggle")
async def toggle_quiz_status(cb: CallbackQuery, session: AsyncSession) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return
    service = AdminService(session)
    s = await service.get_settings()

    if s.finished:
        await cb.answer("Test yakunlangan. Qayta faollantirish mumkin emas.", show_alert=True)
        return

    if s.waiting:
        # Currently waiting, so activate it
        await service.set_quiz_waiting(False)
        await cb.answer("Test faollashtirildi ✅")
    else:
        # Currently active, so pause it
        await service.set_quiz_waiting(True)
        await cb.answer("Test to'xtatildi (waiting mode).")

    s = await service.get_settings()
    await cb.message.edit_text(
        _format_settings_text(s),
        reply_markup=inline.quiz_settings_full_keyboard(
            s.active,
            s.waiting,
            s.finished,
            _require_phone_enabled(s),
            s.quiz_type.value,
        )
    )


@router.callback_query(F.data.startswith("qt:"))
async def set_quiz_type(cb: CallbackQuery, session: AsyncSession) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return
    qt = cb.data.split(":")[1]
    try:
        quiz_type = QuizType(qt)
    except ValueError:
        await cb.answer("Noto'g'ri tur.")
        return
    service = AdminService(session)
    await service.set_quiz_type(quiz_type)
    s = await service.get_settings()
    await cb.message.edit_text(
        _format_settings_text(s),
        reply_markup=inline.quiz_settings_full_keyboard(
            s.active,
            s.waiting,
            s.finished,
            _require_phone_enabled(s),
            s.quiz_type.value,
        )
    )
    await cb.answer(f"Test turi: {quiz_type.value.upper()}", show_alert=True)


@router.message(F.text.in_({"⏸ Testni to'xtatish", "/quiz_wait", "Testni stop qilish"}))
async def set_waiting(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    await AdminService(session).set_quiz_waiting(True)
    await message.answer("Test to'xtatildi (waiting mode).")


@router.message(F.text.in_({"▶️ Testni boshlash", "/quiz_start", "Testni start qilish"}))
async def set_active(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    service = AdminService(session)
    await service.set_quiz_waiting(False)
    await service.set_quiz_finished(False)
    await message.answer("Test boshlandi ✅")


@router.message(F.text.in_({"🏁 Testni yakunlash", "/quiz_finish"}))
async def set_finished(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    await AdminService(session).set_quiz_finished(True)
    await message.answer("Test yakunlandi 🏁")


@router.callback_query(F.data == "ps:phone")
async def toggle_phone_setting(cb: CallbackQuery, session: AsyncSession) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return
    service = AdminService(session)
    await service.toggle_require_phone()
    s = await service.get_settings()
    phone_status = "✅ Talab" if _require_phone_enabled(s) else "❌ Ixtiyoriy"
    await cb.answer(f"Telefon: {phone_status}")
    await cb.message.edit_text(
        _format_settings_text(s),
        reply_markup=inline.quiz_settings_full_keyboard(
            s.active,
            s.waiting,
            s.finished,
            _require_phone_enabled(s),
            s.quiz_type.value,
        )
    )
