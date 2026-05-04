from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.keyboards import inline
from bots.kitobxon.services import ResultsService

router = Router(name="results")


def _format_time(seconds: int) -> str:
    """Format seconds to 'Xm Ys' format"""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}m {secs}s"


@router.message(F.text == "🌟 Natijalar")
async def show_results(message: Message, session: AsyncSession) -> None:
    service = ResultsService(session)
    result = await service.get_user_result(message.from_user.id)

    lines = ["<b>🌟 Natijalar</b>\n"]

    if result:
        status = "✅ O'tdingiz" if result.passed else "❌ O'ta olmadingiz"
        lines.append(
            f"Sizning natijangiz: <b>{result.user.score}/{result.total_questions}</b> — {status}\n"
        )
    else:
        lines.append("Siz hali test yechmagansiz.\n")

    await message.answer(
        "\n".join(lines),
        reply_markup=inline.results_main_keyboard(),
    )


@router.callback_query(F.data == "res_test")
async def show_test_results(cb: CallbackQuery, session: AsyncSession) -> None:
    service = ResultsService(session)
    result = await service.get_detailed_test_result(cb.from_user.id)

    if not result:
        await cb.answer("Test natijalari topilmadi.", show_alert=True)
        return

    status = "✅ O'tdingiz" if result.passed else "❌ O'ta olmadingiz"
    time_str = _format_time(result.total_time_seconds)

    text = (
        f"<b>📊 Test natijalari</b>\n\n"
        f"<b>To'g'ri:</b> {result.correct_count}/{result.total_questions}\n"
        f"<b>Vaqt sarflagan:</b> {time_str}\n"
        f"<b>Status:</b> {status}"
    )

    await cb.message.edit_text(
        text,
        reply_markup=inline.results_back_keyboard(),
    )
    await cb.answer()


@router.callback_query(F.data == "res_referral")
async def show_referral_results(cb: CallbackQuery, session: AsyncSession) -> None:
    service = ResultsService(session)
    user_ref_top = await service.top_by_referrals(cb.from_user.id, limit=10)

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
        lines.append("<b>🏆 Referral bo'yicha top 10:</b>")
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

    lines = ["<b>🌟 Natijalar</b>\n"]

    if result:
        status = "✅ O'tdingiz" if result.passed else "❌ O'ta olmadingiz"
        lines.append(
            f"Sizning natijangiz: <b>{result.user.score}/{result.total_questions}</b> — {status}\n"
        )
    else:
        lines.append("Siz hali test yechmagansiz.\n")

    await cb.message.edit_text(
        "\n".join(lines),
        reply_markup=inline.results_main_keyboard(),
    )
    await cb.answer()
