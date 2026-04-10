from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Document, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.keyboards import inline, reply
from bots.kitobxon.services import AdminService
from bots.kitobxon.states import AdminQuestionStates
from core.logging import get_logger

logger = get_logger(__name__)
router = Router(name="admin_questions")


async def _is_admin(session: AsyncSession, telegram_id: int) -> bool:
    from bots.kitobxon.repositories import UserRepository
    user = await UserRepository(session).get_by_telegram_id(telegram_id)
    return bool(user and user.is_admin)


@router.message(F.text == "❓ Savollar")
async def questions_menu(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    questions = await AdminService(session).list_questions()
    count = len(questions)
    await message.answer(
        f"Jami savollar: <b>{count}</b>",
        reply_markup=inline.questions_list_keyboard(questions),
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


@router.message(AdminQuestionStates.waiting_text)
async def q_text(message: Message, state: FSMContext) -> None:
    await state.update_data(q_text=message.text.strip())
    await state.set_state(AdminQuestionStates.waiting_correct)
    await message.answer("To'g'ri javobni kiriting:")


@router.message(AdminQuestionStates.waiting_correct)
async def q_correct(message: Message, state: FSMContext) -> None:
    await state.update_data(q_correct=message.text.strip())
    await state.set_state(AdminQuestionStates.waiting_wrong_1)
    await message.answer("1-noto'g'ri javobni kiriting:")


@router.message(AdminQuestionStates.waiting_wrong_1)
async def q_wrong1(message: Message, state: FSMContext) -> None:
    await state.update_data(q_wrong1=message.text.strip())
    await state.set_state(AdminQuestionStates.waiting_wrong_2)
    await message.answer("2-noto'g'ri javobni kiriting:")


@router.message(AdminQuestionStates.waiting_wrong_2)
async def q_wrong2(message: Message, state: FSMContext) -> None:
    await state.update_data(q_wrong2=message.text.strip())
    await state.set_state(AdminQuestionStates.waiting_wrong_3)
    await message.answer("3-noto'g'ri javobni kiriting:")


@router.message(AdminQuestionStates.waiting_wrong_3)
async def q_wrong3(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    data = await state.get_data()
    await AdminService(session).add_question(
        text=data["q_text"],
        correct=data["q_correct"],
        wrong_1=data["q_wrong1"],
        wrong_2=data["q_wrong2"],
        wrong_3=message.text.strip(),
    )
    await state.clear()
    await message.answer("Savol qo'shildi ✅", reply_markup=reply.admin_panel())


# Excel import
@router.message(F.document, F.document.mime_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
async def import_questions_excel(
    message: Message, session: AsyncSession, bot: Bot
) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    from bots.kitobxon.utils.excel import import_questions_from_excel
    import tempfile, os
    file = await bot.get_file(message.document.file_id)
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        await bot.download_file(file.file_path, tmp.name)
        tmp_path = tmp.name
    try:
        questions = import_questions_from_excel(tmp_path)
        added = 0
        service = AdminService(session)
        for q in questions:
            await service.add_question(**q)
            added += 1
        await message.answer(f"✅ {added} ta savol import qilindi.")
    except Exception as exc:
        logger.exception("Excel import error: %s", exc)
        await message.answer(f"Xato: {exc}")
    finally:
        os.unlink(tmp_path)
