from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.filters import StateFilter
from aiogram.types import BufferedInputFile, CallbackQuery, Document, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.keyboards import inline, reply
from bots.kitobxon.services import AdminService
from bots.kitobxon.states import AdminImportStates, AdminQuestionStates, AdminQuestionImportStates
from core.logging import get_logger

logger = get_logger(__name__)
router = Router(name="admin_questions")


async def _is_admin(session: AsyncSession, telegram_id: int) -> bool:
    from bots.kitobxon.repositories import UserRepository
    user = await UserRepository(session).get_by_telegram_id(telegram_id)
    return bool(user and user.is_admin)


@router.message(F.text.in_({"❓ Savollar", "Savollar ro'yxati"}))
async def questions_menu(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    questions = await AdminService(session).list_questions()
    count = len(questions)
    await message.answer(
        f"Jami savollar: <b>{count}</b>",
        reply_markup=inline.questions_list_keyboard(questions),
    )


@router.callback_query(F.data == "q_export")
async def export_questions(cb: CallbackQuery, session: AsyncSession) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return
    from bots.kitobxon.utils.excel import export_questions_to_excel
    questions = await AdminService(session).list_questions()
    buf = export_questions_to_excel(questions)
    await cb.message.answer_document(
        document=BufferedInputFile(buf.read(), filename="savollar.xlsx"),
        caption=f"Jami: {len(questions)} savol",
    )
    await cb.answer()


@router.message(F.text == "Savolni export qilish 📤")
async def export_questions_message(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    from bots.kitobxon.utils.excel import export_questions_to_excel

    questions = await AdminService(session).list_questions()
    buf = export_questions_to_excel(questions)
    await message.answer_document(
        document=BufferedInputFile(buf.read(), filename="savollar.xlsx"),
        caption=f"Jami: {len(questions)} savol",
    )


@router.callback_query(F.data.startswith("q_del:"))
async def delete_question(cb: CallbackQuery, session: AsyncSession) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return
    q_id = int(cb.data.split(":")[1])
    service = AdminService(session)
    await service.delete_question(q_id)
    questions = await service.list_questions()
    await cb.message.edit_reply_markup(
        reply_markup=inline.questions_list_keyboard(questions)
    )
    await cb.answer("O'chirildi.")


@router.callback_query(F.data == "q_template")
async def download_template(cb: CallbackQuery, session: AsyncSession) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return
    from bots.kitobxon.utils.excel import generate_questions_template
    buf, ext = generate_questions_template()
    await cb.message.answer_document(
        document=BufferedInputFile(buf.read(), filename=f"savollar_namuna.{ext}"),
        caption="📄 Savollar uchun namuna fayl.\n\nIltimos, ushbu formatda to'ldirib, qayta yuklang.",
    )
    await cb.answer()


@router.message(F.text == "Namuna olish 📄")
async def download_template_message(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    from bots.kitobxon.utils.excel import generate_questions_template

    buf, ext = generate_questions_template()
    await message.answer_document(
        document=BufferedInputFile(buf.read(), filename=f"savollar_namuna.{ext}"),
        caption="📄 Savollar uchun namuna fayl.\n\nIltimos, ushbu formatda to'ldirib, qayta yuklang.",
    )


@router.callback_query(F.data == "q_add")
async def start_add_question(
    cb: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return
    await state.set_state(AdminQuestionStates.waiting_text)
    await cb.message.answer("Savol matnini kiriting:", reply_markup=reply.cancel_only())
    await cb.answer()


@router.message(AdminQuestionStates.waiting_text, F.text == "Bekor qilish")
async def cancel_q_text(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=reply.admin_panel())


@router.message(AdminQuestionStates.waiting_text)
async def q_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Savol matnini yuboring.")
        return
    await state.update_data(q_text=text)
    await state.set_state(AdminQuestionStates.waiting_correct)
    await message.answer("To'g'ri javobni kiriting:", reply_markup=reply.cancel_only())


@router.message(AdminQuestionStates.waiting_correct, F.text == "Bekor qilish")
async def cancel_q_correct(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=reply.admin_panel())


@router.message(AdminQuestionStates.waiting_correct)
async def q_correct(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("To'g'ri javobni yuboring.")
        return
    await state.update_data(q_correct=text)
    await state.set_state(AdminQuestionStates.waiting_wrong_1)
    await message.answer("1-noto'g'ri javobni kiriting:", reply_markup=reply.cancel_only())


@router.message(AdminQuestionStates.waiting_wrong_1, F.text == "Bekor qilish")
async def cancel_q_wrong1(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=reply.admin_panel())


@router.message(AdminQuestionStates.waiting_wrong_1)
async def q_wrong1(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("1-noto'g'ri javobni yuboring.")
        return
    await state.update_data(q_wrong1=text)
    await state.set_state(AdminQuestionStates.waiting_wrong_2)
    await message.answer("2-noto'g'ri javobni kiriting:", reply_markup=reply.cancel_only())


@router.message(AdminQuestionStates.waiting_wrong_2, F.text == "Bekor qilish")
async def cancel_q_wrong2(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=reply.admin_panel())


@router.message(AdminQuestionStates.waiting_wrong_2)
async def q_wrong2(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("2-noto'g'ri javobni yuboring.")
        return
    await state.update_data(q_wrong2=text)
    await state.set_state(AdminQuestionStates.waiting_wrong_3)
    await message.answer("3-noto'g'ri javobni kiriting:", reply_markup=reply.cancel_only())


@router.message(AdminQuestionStates.waiting_wrong_3, F.text == "Bekor qilish")
async def cancel_q_wrong3(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=reply.admin_panel())


@router.message(AdminQuestionStates.waiting_wrong_3)
async def q_wrong3(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("3-noto'g'ri javobni yuboring.")
        return
    await state.update_data(q_wrong3=text)
    data = await state.get_data()

    # Show confirmation message
    confirmation_text = (
        "<b>Savol tasdiqlash:</b>\n\n"
        f"<b>Savol:</b> {data['q_text']}\n\n"
        f"<b>To'g'ri javob:</b> {data['q_correct']}\n"
        f"<b>Noto'g'ri 1:</b> {data['q_wrong1']}\n"
        f"<b>Noto'g'ri 2:</b> {data['q_wrong2']}\n"
        f"<b>Noto'g'ri 3:</b> {data['q_wrong3']}"
    )

    await state.set_state(AdminQuestionStates.waiting_confirmation)
    await message.answer(confirmation_text, reply_markup=reply.confirm_action())


@router.message(AdminQuestionStates.waiting_confirmation, F.text == "✅ Qo'shish")
async def confirm_add_question(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    await AdminService(session).add_question(
        text=data["q_text"],
        correct=data["q_correct"],
        wrong_1=data["q_wrong1"],
        wrong_2=data["q_wrong2"],
        wrong_3=data["q_wrong3"],
    )
    await state.clear()
    await message.answer("Savol qo'shildi ✅", reply_markup=reply.admin_panel())


@router.message(AdminQuestionStates.waiting_confirmation, F.text == "❌ Bekor qilish")
async def cancel_add_question_confirmation(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=reply.admin_panel())


@router.callback_query(F.data == "q_import_start")
async def start_import_questions(
    cb: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return
    await state.set_state(AdminQuestionImportStates.waiting_file)
    await cb.message.answer(
        "<b>📥 Savollar faylini yuklang</b>\n\n"
        "Format: .xlsx yoki .csv\n"
        "Ustunlar: Savol, To'g'ri javob, Noto'g'ri 1, Noto'g'ri 2, Noto'g'ri 3\n\n"
        "Namuna olish uchun savollar ro'yxatiga qaytib, 'Namuna' tugmasini bosing.",
        reply_markup=reply.cancel_only(),
    )
    await cb.answer()


@router.message(F.text == "Savol yuklash 📥")
async def start_import_questions_message(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    await state.set_state(AdminQuestionImportStates.waiting_file)
    await message.answer(
        "<b>📥 Savollar faylini yuklang</b>\n\n"
        "Format: .xlsx yoki .csv\n"
        "Ustunlar: Savol, To'g'ri javob, Noto'g'ri 1, Noto'g'ri 2, Noto'g'ri 3",
        reply_markup=reply.cancel_only(),
    )


@router.message(AdminQuestionImportStates.waiting_file, F.text == "Bekor qilish")
async def cancel_import_questions(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=reply.admin_panel())


# Excel/CSV import
@router.message(
    F.document,
    F.document.mime_type.in_(
        [
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/csv",
        ]
    ),
    ~StateFilter(AdminImportStates.waiting_users_file),
)
async def import_questions_excel(
    message: Message, session: AsyncSession, bot: Bot
) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    from bots.kitobxon.utils.excel import import_questions_from_excel
    import tempfile, os

    # Determine file extension from document name
    filename = message.document.file_name or "file.xlsx"
    ext = ".csv" if filename.lower().endswith(".csv") else ".xlsx"

    file = await bot.get_file(message.document.file_id)
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        await bot.download_file(file.file_path, tmp.name)
        tmp_path = tmp.name
    try:
        questions, errors = import_questions_from_excel(tmp_path)
        added = 0
        service = AdminService(session)
        for q in questions:
            await service.add_question(**q)
            added += 1

        result_msg = f"✅ <b>{added} ta savol import qilindi.</b>"

        if errors:
            result_msg += f"\n\n❌ <b>Xatoliklar ({len(errors)} ta):</b>\n"
            for err in errors[:10]:
                result_msg += f"{err}\n"
            if len(errors) > 10:
                result_msg += f"... va yana {len(errors) - 10} ta xatolik."

        await message.answer(result_msg)
    except Exception as exc:
        logger.exception("Import error: %s", exc)
        await message.answer(f"❌ Xato: {exc}")
    finally:
        os.unlink(tmp_path)
