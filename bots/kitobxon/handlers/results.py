from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.services import ResultsService

router = Router(name="results")


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

    # Top by score
    score_top = await service.top_by_score(message.from_user.id, limit=10)
    if score_top:
        lines.append("<b>🏆 Ball bo'yicha top 10:</b>")
        for entry in score_top:
            marker = "👉 " if entry.is_current else ""
            lines.append(
                f"{marker}{entry.rank}. {entry.user.fio or entry.user.username} — {entry.user.score} ball"
            )

    lines.append("")

    # Top by referrals
    ref_top = await service.top_by_referrals(message.from_user.id, limit=10)
    if ref_top:
        lines.append("<b>👥 Referal bo'yicha top 10:</b>")
        for entry in ref_top:
            marker = "👉 " if entry.is_current else ""
            lines.append(
                f"{marker}{entry.rank}. {entry.user.fio or entry.user.username} — {entry.user.referrals_count} ta"
            )

    await message.answer("\n".join(lines))
