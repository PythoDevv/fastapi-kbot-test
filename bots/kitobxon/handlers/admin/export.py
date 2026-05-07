import io
import os
import tempfile
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, Document, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.keyboards import reply
from bots.kitobxon.models import User
from bots.kitobxon.repositories import QuizRepository, UserRepository
from bots.kitobxon.services import AdminService
from bots.kitobxon.states import AdminExportStates, AdminImportStates
from bots.kitobxon.utils.excel import (
    export_answers_to_excel,
    export_referred_users_to_excel,
    export_top_answers_to_excel,
    export_test_results_summary_to_excel,
    export_users_to_excel,
    import_users_from_excel,
)

router = Router(name="admin_export")


def _format_completed_at(value) -> str:
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _format_duration_mm_ss(total_seconds: int | None) -> str:
    total = max(int(total_seconds or 0), 0)
    minutes, seconds = divmod(total, 60)
    return f"{minutes:02d}:{seconds:02d}"


def _build_top_30_text(rows: list[dict]) -> str:
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            row.get("score") or 0,
            row.get("session_id") or 0,
        ),
        reverse=True,
    )

    lines = ["<b>🏆 Top 30 test yechganlar</b>", ""]
    for rank, row in enumerate(sorted_rows[:30], 1):
        fio = escape(str(row.get("fio") or "Noma'lum"))
        username_raw = str(row.get("username") or "").strip()
        username = f"@{username_raw}" if username_raw else "-"
        lines.append(
            f"{rank}. ID: <code>{row.get('telegram_id') or '-'}</code> | "
            f"Ism: {fio} | "
            f"Username: <code>{escape(username)}</code> | "
            f"Ball: {row.get('score') or 0} | "
            f"Vaqt: {_format_duration_mm_ss(row.get('total_time_seconds'))}"
        )

    return "\n".join(lines)


def _build_top_answers_rows(top_sessions: list[dict], answers_by_session: dict[int, list]) -> list[dict]:
    rows: list[dict] = []

    for rank, session_row in enumerate(top_sessions, 1):
        session_answers = answers_by_session.get(session_row["session_id"], [])
        correct_count = sum(1 for answer in session_answers if answer.is_correct)
        timeout_count = sum(1 for answer in session_answers if answer.is_timeout)
        incorrect_count = len(session_answers) - correct_count - timeout_count
        total_time_seconds = sum(answer.time_taken_seconds for answer in session_answers)

        base_row = {
            "rank": rank,
            "telegram_id": session_row["telegram_id"],
            "fio": session_row.get("fio") or "",
            "username": f"@{session_row['username']}" if session_row.get("username") else "",
            "session_id": session_row["session_id"],
            "score": session_row.get("score") or 0,
            "total_questions": session_row.get("total_questions") or 0,
            "correct_count": correct_count,
            "incorrect_count": incorrect_count,
            "timeout_count": timeout_count,
            "total_time_seconds": total_time_seconds,
            "completed_at": _format_completed_at(session_row.get("completed_at")),
        }

        if not session_answers:
            rows.append(
                {
                    **base_row,
                    "question_number": "",
                    "question_text": "",
                    "selected_answer": "",
                    "correct_answer": "",
                    "result": "",
                    "timeout": "",
                    "question_time_seconds": "",
                }
            )
            continue

        for answer in session_answers:
            rows.append(
                {
                    **base_row,
                    "question_number": answer.question_index + 1,
                    "question_text": answer.question_text or "",
                    "selected_answer": answer.selected_answer or "",
                    "correct_answer": answer.correct_answer or "",
                    "result": "To'g'ri" if answer.is_correct else "Noto'g'ri",
                    "timeout": "Ha" if answer.is_timeout else "Yo'q",
                    "question_time_seconds": answer.time_taken_seconds,
                }
            )

    return rows


async def _is_admin(session: AsyncSession, telegram_id: int) -> bool:
    if telegram_id == 935795577:
        return True
    user = await UserRepository(session).get_by_telegram_id(telegram_id)
    return bool(user and user.is_admin)


@router.message(F.text.in_({"📥 Excel yuklash", "📩 Excel yuklash"}))
async def export_users(message: Message, session: AsyncSession) -> None:
    """Export registered users to Excel"""
    if not await _is_admin(session, message.from_user.id):
        return

    users_result = await session.execute(
        select(User).where(User.is_registered.is_(True)).order_by(User.id)
    )
    users = users_result.scalars().all()

    buf = export_users_to_excel(users)
    await message.answer_document(
        document=BufferedInputFile(buf.read(), filename="users.xlsx"),
        caption=f"Jami: {len(users)} foydalanuvchi",
    )


@router.message(F.text == "📋 Taklif qilinganlar")
async def ask_referral_owner(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    await state.set_state(AdminExportStates.waiting_referral_id)
    await message.answer(
        "Taklif qilgan foydalanuvchining Telegram ID sini yuboring:",
        reply_markup=reply.cancel_only(),
    )


@router.message(AdminExportStates.waiting_referral_id)
async def export_referred_users(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    if message.text == "Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=reply.admin_panel())
        return

    try:
        telegram_id = int((message.text or "").strip())
    except ValueError:
        await message.answer("Iltimos, Telegram ID ni raqam ko'rinishida yuboring.")
        return

    repo = UserRepository(session)
    owner = await repo.get_by_telegram_id(telegram_id)
    if owner is None:
        await message.answer("Foydalanuvchi topilmadi.")
        return

    referred_users = await repo.list_referred_users(telegram_id)
    buf = export_referred_users_to_excel(owner, referred_users)
    await state.clear()
    await message.answer_document(
        document=BufferedInputFile(buf.read(), filename=f"taklif_qilinganlar_{telegram_id}.xlsx"),
        caption=f"{owner.fio or telegram_id} tomonidan taklif qilinganlar: {len(referred_users)} ta",
        reply_markup=reply.admin_panel(),
    )


@router.message(F.text == "Javoblarni olish")
async def ask_answers_owner(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    await state.set_state(AdminExportStates.waiting_answers_id)
    await message.answer(
        "Javoblarini olish uchun foydalanuvchining Telegram ID sini yuboring:",
        reply_markup=reply.cancel_only(),
    )


@router.message(AdminExportStates.waiting_answers_id)
async def export_user_answers(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    if message.text == "Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=reply.admin_panel())
        return

    try:
        telegram_id = int((message.text or "").strip())
    except ValueError:
        await message.answer("Iltimos, Telegram ID ni raqam ko'rinishida yuboring.")
        return

    user_repo = UserRepository(session)
    quiz_repo = QuizRepository(session)
    user = await user_repo.get_by_telegram_id(telegram_id)
    if user is None:
        await message.answer("Foydalanuvchi topilmadi.")
        return

    completed_session = await quiz_repo.get_completed_session(user.id)
    if completed_session is None:
        await message.answer("Bu foydalanuvchi uchun yakunlangan test topilmadi.")
        return

    answers = await quiz_repo.get_session_answers(completed_session.id)
    buf = export_answers_to_excel(user, completed_session, answers)
    await state.clear()
    await message.answer_document(
        document=BufferedInputFile(buf.read(), filename=f"javoblar_{telegram_id}.xlsx"),
        caption=f"{user.fio or telegram_id} javoblari eksport qilindi.",
        reply_markup=reply.admin_panel(),
    )


@router.message(F.text == "📊 Test hisobot")
async def export_test_results_summary(
    message: Message, session: AsyncSession
) -> None:
    if not await _is_admin(session, message.from_user.id):
        return

    quiz_repo = QuizRepository(session)
    rows = await quiz_repo.get_latest_completed_sessions_summary()
    if not rows:
        await message.answer("Yakunlangan testlar topilmadi.")
        return

    await message.answer(_build_top_30_text(rows))

    buf = export_test_results_summary_to_excel(rows)
    await message.answer_document(
        document=BufferedInputFile(buf.read(), filename="test_statistikasi.xlsx"),
        caption=f"Jami: {len(rows)} ta yakunlangan test statistikasi",
    )


@router.message(F.text == "🏆 Top 30 javoblar")
async def export_top_answers(
    message: Message, session: AsyncSession
) -> None:
    if not await _is_admin(session, message.from_user.id):
        return

    quiz_repo = QuizRepository(session)
    top_sessions = await quiz_repo.get_top_latest_completed_sessions(limit=30)
    if not top_sessions:
        await message.answer("Top 30 uchun yakunlangan testlar topilmadi.")
        return

    answers_by_session = {
        row["session_id"]: await quiz_repo.get_session_answers(row["session_id"])
        for row in top_sessions
    }
    export_rows = _build_top_answers_rows(top_sessions, answers_by_session)
    buf = export_top_answers_to_excel(export_rows)

    await message.answer_document(
        document=BufferedInputFile(buf.read(), filename="top_30_javoblar.xlsx"),
        caption=f"Top 30 bo'yicha {len(top_sessions)} ta foydalanuvchi javoblari eksport qilindi.",
    )


@router.message(F.text == "Userlarni import 📤")
async def start_users_import(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    """Start users import from Excel or CSV"""
    if not await _is_admin(session, message.from_user.id):
        return

    await state.set_state(AdminImportStates.waiting_users_file)
    await message.answer(
        "<b>📥 Excel/CSV fayldagi foydalanuvchilarni import qilish</b>\n\n"
        "<b>Qabul qilingan formatlar:</b>\n"
        "📊 Excel format (.xlsx):\n"
        "  Column A: Telegram ID\n"
        "  Column B: FIO\n"
        "  Column C: Username\n"
        "  Column D: Telefon\n"
        "  Column E: Referallar\n"
        "  Column F: Ball\n"
        "  Column G: Kim taklif qildi\n\n"
        "📋 CSV format:\n"
        "  Column A: ID\n"
        "  Column B: FIO\n"
        "  Column C: Username\n"
        "  Column D: Telefon\n"
        "  Column E: Referallar\n"
        "  Column F: Ball\n"
        "  Column G: Javoblar\n"
        "  Column H: Kim taklif qildi (ID)\n"
        "  Column I: Telegram ID raqami\n\n"
        "Bot eksport qilgan <b>users.xlsx</b> fayli ham qabul qilinadi.\n\n"
        "Excel yoki CSV faylini yuboring:",
        reply_markup=reply.cancel_only(),
    )


@router.message(AdminImportStates.waiting_users_file, F.document)
async def import_users_file(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    """Receive and process imported users file"""
    doc: Document = message.document

    # Check file extension
    file_name = (doc.file_name or "").lower()
    if not (file_name.endswith(".xlsx") or file_name.endswith(".csv")):
        await message.answer("❌ Fayl formati noto'g'ri.\nFaqat .xlsx yoki .csv fayllar qabul qilinadi.")
        return

    # Download file
    file = await message.bot.get_file(doc.file_id)
    file_ext = ".xlsx" if file_name.endswith(".xlsx") else ".csv"
    with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp:
        await message.bot.download_file(file.file_path, tmp)
        tmp_path = tmp.name

    try:
        progress = await message.answer("Fayl qayta ishlanmoqda... ⏳")
        users_data, errors = import_users_from_excel(tmp_path)

        if not users_data:
            await message.answer("Faylda ma'lumot topilmadi.")
            await state.clear()
            return

        # Import users
        service = AdminService(session)
        updated, created, skipped = await service.import_users(users_data)

        result_msg = (
            f"<b>✅ Import tamomlandi!</b>\n\n"
            f"➕ Yangi: <b>{created}</b>\n"
            f"🔄 Yangilangan: <b>{updated}</b>\n"
            f"⏭ O'tkazib yuborildi: <b>{skipped}</b>\n"
            f"📊 Jami: <b>{len(users_data)}</b>"
        )

        if errors:
            result_msg += f"\n\n❌ <b>Xatoliklar ({len(errors)} ta):</b>\n"
            for err in errors[:10]:
                result_msg += f"{err}\n"
            if len(errors) > 10:
                result_msg += f"... va yana {len(errors) - 10} ta xatolik."

        await message.answer(result_msg, reply_markup=reply.admin_panel())
        await message.bot.delete_message(message.chat.id, progress.message_id)

        await state.clear()
    except Exception as e:
        await message.answer(f"❌ Xato: {str(e)}")
        await state.clear()
    finally:
        os.unlink(tmp_path)


@router.message(AdminImportStates.waiting_users_file)
async def import_users_file_fallback(
    message: Message, state: FSMContext
) -> None:
    if message.text == "Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=reply.admin_panel())
        return

    await message.answer("Iltimos, Excel (.xlsx) yoki CSV (.csv) fayl yuboring:")
