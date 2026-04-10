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
        "Excel yoki CSV faylini yuboring:",
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
        await message.answer("Iltimos, Excel (.xlsx) yoki CSV (.csv) fayl yuboring:")
        return

    doc: Document = message.document

    # Check file extension
    file_name = doc.file_name or ""
    if not (file_name.endswith('.xlsx') or file_name.endswith('.csv')):
        await message.answer("❌ Fayl formati noto'g'ri.\nFaqat .xlsx yoki .csv fayllar qabul qilinadi.")
        return

    # Download file
    file = await message.bot.get_file(doc.file_id)
    file_ext = ".xlsx" if file_name.endswith('.xlsx') else ".csv"
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
