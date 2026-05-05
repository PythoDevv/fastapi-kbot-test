from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.keyboards import inline
from bots.kitobxon.services import ResultsService

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


def _format_user_line(rank: int, user, score: int, current: bool) -> str:
    name = user.fio or user.username or "-"
    prefix = "👉 " if current else ""
    return f"{prefix}{rank}. {name} — {score} ball"


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
    top_scores = await service.top_by_score(message.from_user.id)
    top_test_takers = await service.top_test_takers(message.from_user.id)

    lines = ["<b>🌟 Natijalar</b>\n"]

    if result:
        status = "✅ O'tdingiz" if result.passed else "❌ O'ta olmadingiz"
        lines.append(
            f"Sizning natijangiz: <b>{result.user.score}/{result.total_questions}</b> — {status}\n"
        )
    else:
        lines.append("Siz hali test yechmagansiz.\n")

    if top_scores:
        lines.append("<b>🏆 Top 30 umumiy ball bo'yicha</b>")
        for entry in top_scores:
            lines.append(_format_user_line(entry.rank, entry.user, entry.user.score or 0, entry.is_current))
        lines.append("")

    if top_test_takers:
        lines.append("<b>📝 Top 30 test yechganlar</b>")
        for entry in top_test_takers:
            lines.append(_format_user_line(entry.rank, entry.user, entry.user.score or 0, entry.is_current))

    parts = _split_text("\n".join(lines))
    await _send_text_parts(message, parts, keyboard=inline.results_main_keyboard())


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
    top_scores = await service.top_by_score(cb.from_user.id)
    top_test_takers = await service.top_test_takers(cb.from_user.id)

    lines = ["<b>🌟 Natijalar</b>\n"]

    if result:
        status = "✅ O'tdingiz" if result.passed else "❌ O'ta olmadingiz"
        lines.append(
            f"Sizning natijangiz: <b>{result.user.score}/{result.total_questions}</b> — {status}\n"
        )
    else:
        lines.append("Siz hali test yechmagansiz.\n")

    if top_scores:
        lines.append("<b>🏆 Top 30 umumiy ball bo'yicha</b>")
        for entry in top_scores:
            lines.append(_format_user_line(entry.rank, entry.user, entry.user.score or 0, entry.is_current))
        lines.append("")

    if top_test_takers:
        lines.append("<b>📝 Top 30 test yechganlar</b>")
        for entry in top_test_takers:
            lines.append(_format_user_line(entry.rank, entry.user, entry.user.score or 0, entry.is_current))

    text = "\n".join(lines)
    parts = _split_text(text)

    if len(parts) == 1:
        await cb.message.edit_text(parts[0], reply_markup=inline.results_main_keyboard())
    else:
        await cb.message.edit_text(parts[0], reply_markup=inline.results_main_keyboard())
        for part in parts[1:]:
            await cb.message.answer(part)

    await cb.answer()
