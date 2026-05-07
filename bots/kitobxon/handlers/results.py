from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.keyboards import inline
from bots.kitobxon.services import ResultsService
from bots.kitobxon.utils.certificate import build_certificate_input_file, generate_certificate

router = Router(name="results")


def _split_text(text: str) -> list[str]:
    parts: list[str] = []
    while text:
        if len(text) > 4000:
            cut_idx = text.rfind("\n", 0, 4000)
            if cut_idx == -1:
                cut_idx = 4000
            parts.append(text[:cut_idx])
            text = text[cut_idx:]
        else:
            parts.append(text)
            break
    return parts


def _format_user_line(
    rank: int,
    user,
    value: int,
    current: bool,
    suffix: str = "ball",
) -> str:
    name = user.fio or user.username or "-"
    prefix = "👉 " if current else ""
    return f"{prefix}{rank}. {name} — {value} {suffix}"


def _format_time(seconds: int) -> str:
    """Format seconds to 'Xm Ys' format"""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}m {secs}s"


async def _send_text_parts(message, parts: list[str], keyboard=None) -> None:
    for idx, part in enumerate(parts, start=1):
        if idx == len(parts) and keyboard is not None:
            await message.answer(part, reply_markup=keyboard)
        else:
            await message.answer(part)


@router.message(F.text == "🌟 Natijalar")
async def show_results(message: Message, session: AsyncSession) -> None:
    service = ResultsService(session)
    result = await service.get_user_result(message.from_user.id)
    detailed_result = await service.get_detailed_test_result(message.from_user.id)
    top_referrals = await service.top_by_referrals(message.from_user.id, limit=30)
    top_test_takers = await service.top_test_takers(message.from_user.id)

    lines = ["<b>🌟 Natijalar</b>\n"]

    if result:
        time_line = ""
        if detailed_result:
            time_line = f"\nSarflagan vaqt: <b>{_format_time(detailed_result.total_time_seconds)}</b>"
        lines.append(
            f"Sizning natijangiz: <b>{result.final_score}/{result.total_questions}</b> — {time_line}\n"
        )
    else:
        lines.append("Siz hali test yechmagansiz.\n")

    if top_referrals:
        lines.append("<b>🏆 Top 30 referal bo'yicha</b>")
        for entry in top_referrals:
            lines.append(
                _format_user_line(
                    entry.rank,
                    entry.user,
                    entry.value,
                    entry.is_current,
                    "ta",
                )
            )
        lines.append("")

    if top_test_takers:
        lines.append("<b>📝 Top 30 test yechganlar</b>")
        for entry in top_test_takers:
            lines.append(_format_user_line(entry.rank, entry.user, entry.value, entry.is_current))

    parts = _split_text("\n".join(lines))
    await _send_text_parts(message, parts, keyboard=inline.results_main_keyboard())


@router.callback_query(F.data == "res_test")
async def show_test_results(cb: CallbackQuery, session: AsyncSession) -> None:
    service = ResultsService(session)
    result = await service.get_detailed_test_result(cb.from_user.id)

    if not result:
        await cb.answer("Test natijalari topilmadi.", show_alert=True)
        return

    time_str = _format_time(result.total_time_seconds)

    text = (
        f"<b>📊 Test natijalari</b>\n\n"
        f"<b>To'g'ri:</b> {result.correct_count}/{result.total_questions}\n"
        f"<b>Vaqt sarflagan:</b> {time_str}\n"
    )

    await cb.message.edit_text(
        text,
        reply_markup=inline.results_back_keyboard(),
    )
    await cb.answer()


@router.callback_query(F.data == "res_referral")
async def show_referral_results(cb: CallbackQuery, session: AsyncSession) -> None:
    service = ResultsService(session)
    user_ref_top = await service.top_by_referrals(cb.from_user.id, limit=30)

    user_count = None
    for entry in user_ref_top:
        if entry.is_current:
            user_count = entry.user.referrals_count
            break

    lines = ["<b>👥 Referallar</b>\n"]

    if user_count is not None:
        lines.append(f"Siz taklif qilgansiz: <b>{user_count} kishi</b>\n")
    else:
        lines.append("Siz taklif qilmagan edingiz.\n")

    if user_ref_top:
        lines.append("<b>🏆 Referral bo'yicha top 30:</b>")
        for entry in user_ref_top:
            marker = "👉 " if entry.is_current else ""
            lines.append(
                f"{marker}{entry.rank}. {entry.user.fio or entry.user.username} — {entry.user.referrals_count} ta"
            )

    await cb.message.edit_text(
        "\n".join(lines),
        reply_markup=inline.results_back_keyboard(),
    )
    await cb.answer()


@router.callback_query(F.data == "res_back")
async def back_to_results(cb: CallbackQuery, session: AsyncSession) -> None:
    service = ResultsService(session)
    result = await service.get_user_result(cb.from_user.id)
    detailed_result = await service.get_detailed_test_result(cb.from_user.id)
    top_referrals = await service.top_by_referrals(cb.from_user.id, limit=30)
    top_test_takers = await service.top_test_takers(cb.from_user.id)

    lines = ["<b>🌟 Natijalar</b>\n"]

    if result:
        time_line = ""
        if detailed_result:
            time_line = f"\nSarflagan vaqt: <b>{_format_time(detailed_result.total_time_seconds)}</b>"
        lines.append(
            f"Sizning natijangiz: <b>{result.final_score}/{result.total_questions}</b> — {time_line}\n"
        )
    else:
        lines.append("Siz hali test yechmagansiz.\n")

    if top_referrals:
        lines.append("<b>🏆 Top 30 referal bo'yicha</b>")
        for entry in top_referrals:
            lines.append(
                _format_user_line(
                    entry.rank,
                    entry.user,
                    entry.value,
                    entry.is_current,
                    "ta",
                )
            )
        lines.append("")

    if top_test_takers:
        lines.append("<b>📝 Top 30 test yechganlar</b>")
        for entry in top_test_takers:
            lines.append(_format_user_line(entry.rank, entry.user, entry.value, entry.is_current))

    text = "\n".join(lines)
    parts = _split_text(text)

    if len(parts) == 1:
        await cb.message.edit_text(parts[0], reply_markup=inline.results_main_keyboard())
    else:
        await cb.message.edit_text(parts[0], reply_markup=inline.results_main_keyboard())
        for part in parts[1:]:
            await cb.message.answer(part)


@router.message(F.text == "🎖 Mening sertifikatim")
async def show_my_certificate(message: Message, session: AsyncSession) -> None:
    """Show certificate menu and allow generating/viewing certificate"""
    service = ResultsService(session)
    result = await service.get_user_result(message.from_user.id)
    
    if not result:
        await message.answer(
            "📋 Test yechmagansiz. Test yechib o'tinggach sertifikat olishingiz mumkin.",
            reply_markup=inline.certificate_main_keyboard(has_passed=False),
        )
        return
    
    if not result.passed:
        required_score = 5  # Get from settings if needed
        await message.answer(
            f"❌ Afsuski, siz sertifikat olish uchun etarli ball topmagansiz.\n"
            f"Sizning natijangiz: {result.final_score}/{result.total_questions}\n"
            f"Sertifikat olish uchun: {required_score} ball kerak.",
            reply_markup=inline.certificate_main_keyboard(has_passed=False),
        )
        return
    
    # User has passed - show certificate with option to generate
    text = (
        f"🎖 <b>Tabriklaymiz!</b>\n\n"
        f"Siz sertifikat olishga munosib bo'ldingiz!\n"
        f"Natijangiz: <b>{result.final_score}/{result.total_questions}</b>\n\n"
        f"Sertifikatni yuklash uchun quyidagi tugmani bosing:"
    )
    await message.answer(text, reply_markup=inline.certificate_download_keyboard())


@router.callback_query(F.data == "res_certificate")
async def show_certificate_from_results(cb: CallbackQuery, session: AsyncSession) -> None:
    """Show certificate menu from results"""
    service = ResultsService(session)
    result = await service.get_user_result(cb.from_user.id)
    
    if not result:
        await cb.answer("Test yechmagansiz.", show_alert=True)
        return
    
    if not result.passed:
        required_score = 5
        text = (
            f"❌ Afsuski, siz sertifikat olish uchun etarli ball topmagansiz.\n"
            f"Sizning natijangiz: {result.final_score}/{result.total_questions}\n"
            f"Sertifikat olish uchun: {required_score} ball kerak."
        )
        await cb.message.edit_text(text, reply_markup=inline.results_back_keyboard())
        await cb.answer()
        return
    
    text = (
        f"🎖 <b>Tabriklaymiz!</b>\n\n"
        f"Siz sertifikat olishga munosib bo'ldingiz!\n"
        f"Natijangiz: <b>{result.final_score}/{result.total_questions}</b>\n\n"
        f"Sertifikatni yuklash uchun quyidagi tugmani bosing:"
    )
    await cb.message.edit_text(text, reply_markup=inline.certificate_from_results_keyboard())
    await cb.answer()


@router.callback_query(F.data == "cert_generate")
async def generate_and_send_certificate(cb: CallbackQuery, session: AsyncSession) -> None:
    """Generate and send certificate to user"""
    from bots.kitobxon.repositories import UserRepository
    
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(cb.from_user.id)
    
    if not user or not user.is_registered:
        await cb.answer("Foydalanuvchi topilmadi.", show_alert=True)
        return
    
    service = ResultsService(session)
    result = await service.get_user_result(cb.from_user.id)
    
    if not result or not result.passed:
        await cb.answer("Siz sertifikat olish uchun etarli ball topmagansiz.", show_alert=True)
        return
    
    # Generate certificate
    full_name = user.fio or user.username or f"User {user.telegram_id}"
    cert_bytes = generate_certificate(
        full_name=full_name,
        score=result.final_score,
        total=result.total_questions,
        include_total=False,
    )
    
    if not cert_bytes:
        await cb.answer("Sertifikat yaratishda xato yuz berdi.", show_alert=True)
        return
    
    # Mark as certificate_received if not already
    if not user.certificate_received:
        user.certificate_received = True
        await session.flush()
    
    # Send certificate
    await cb.message.answer_document(
        document=build_certificate_input_file(cert_bytes),
        caption=(
            f"🎖 <b>Sertifikat</b>\n\n"
            f"Ism: {full_name}\n\n"
            f"Tabriklaymiz! 🎉"
        ),
    )
    await cb.answer("Sertifikat yuborildi! ✅", show_alert=False)


@router.callback_query(F.data == "cert_back")
async def back_to_certificate_menu(cb: CallbackQuery) -> None:
    """Back from certificate view to menu"""
    text = (
        f"🎖 <b>Mening sertifikatim</b>\n\n"
        f"Sertifikatni yuklash uchun quyidagi tugmani bosing:"
    )
    await cb.message.edit_text(text, reply_markup=inline.certificate_download_keyboard())
    await cb.answer()

    await cb.answer()
