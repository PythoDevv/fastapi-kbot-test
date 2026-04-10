import io
import os
import tempfile

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, Document, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.keyboards import reply
from bots.kitobxon.models import User
from bots.kitobxon.repositories import UserRepository
from bots.kitobxon.services import AdminService
from bots.kitobxon.states import AdminImportStates
from bots.kitobxon.utils.excel import export_users_to_excel, import_users_from_excel

router = Router(name="admin_export")


async def _is_admin(session: AsyncSession, telegram_id: int) -> bool:
    user = await UserRepository(session).get_by_telegram_id(telegram_id)
    return bool(user and user.is_admin)


@router.message(F.text == "📥 Excel yuklash")
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


@router.message(F.text == "Userlarni import 📤")
async def start_users_import(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    """Start users import from Excel"""
    if not await _is_admin(session, message.from_user.id):
        return

    await state.set_state(AdminImportStates.waiting_users_file)
    await message.answer(
        "<b>📥 Excel fayldagi foydalanuvchilarni import qilish</b>\n\n"
        "Format:\n"
        "Column A: Telegram ID\n"
        "Column B: FIO\n"
        "Column C: Username\n"
        "Column D: Telefon raqam\n"
        "Column E: Referallar soni\n"
        "Column F: Ball\n"
        "Column G: Kim taklif qildi (User ID)\n\n"
        "Excel faylini yuboring:",
        reply_markup=reply.cancel_only(),
    )


@router.message(AdminImportStates.waiting_users_file)
async def import_users_file(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    """Receive and process imported users file"""
    if message.text == "Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=reply.admin_panel())
        return

    if not message.document:
        await message.answer("Iltimos, Excel fayl yuboring (.xlsx):")
        return

    doc: Document = message.document

    # Download file
    file = await message.bot.get_file(doc.file_id)
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        await message.bot.download_file(file.file_path, tmp)
        tmp_path = tmp.name

    try:
        users_data = import_users_from_excel(tmp_path)

        if not users_data:
            await message.answer("Faylda ma'lumot topilmadi.")
            await state.clear()
            return

        # Import users
        service = AdminService(session)
        updated, created, skipped = await service.import_users(users_data)

        await state.clear()
        await message.answer(
            f"<b>✅ Import tamomlandi!</b>\n\n"
            f"Yangi foydalanuvchilar: <b>{created}</b>\n"
            f"Yangilangan: <b>{updated}</b>\n"
            f"O'tkazib yuborilgan: <b>{skipped}</b>\n"
            f"Jami: <b>{len(users_data)}</b>",
            reply_markup=reply.admin_panel(),
        )
    except Exception as e:
        await message.answer(f"Xato: {str(e)}")
        await state.clear()
    finally:
        os.unlink(tmp_path)
