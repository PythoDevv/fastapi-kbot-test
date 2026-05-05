from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.keyboards import reply
from bots.kitobxon.services import BroadcastService
from bots.kitobxon.states import BroadcastStates
from core.logging import get_logger

logger = get_logger(__name__)
router = Router(name="broadcast")


@router.message(F.text.in_({"📢 Broadcast", "Reklama jo'natish"}))
async def broadcast_start(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    from bots.kitobxon.repositories import UserRepository
    user = await UserRepository(session).get_by_telegram_id(message.from_user.id)
    if message.from_user.id != 935795577 and (not user or not user.is_admin):
        return
    await state.set_state(BroadcastStates.waiting_message)
    await message.answer(
        "Broadcast uchun xabar yuboring:", reply_markup=reply.cancel_only()
    )


@router.message(BroadcastStates.waiting_message)
async def broadcast_preview(
    message: Message, state: FSMContext
) -> None:
    # Store message type and details for broadcasting
    await state.update_data(
        message_type="text",
        message_id=message.message_id,
        chat_id=message.chat.id,
        message_text=message.text or message.caption or "",
    )
    await state.set_state(BroadcastStates.waiting_confirmation)

    preview_text = message.text or message.caption or "[Stiker yoki boshqa kontentli xabar]"
    await message.answer(
        f"Quyidagi xabar yuboriladi:\n\n{preview_text}\n\nTasdiqlaysizmi?",
        reply_markup=reply.broadcast_confirm(),
    )


@router.message(BroadcastStates.waiting_confirmation, F.text == "✅ Yuborish")
async def broadcast_confirm(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    data = await state.get_data()
    original_message_id = data.get("message_id")
    original_chat_id = data.get("chat_id")
    await state.clear()

    status_msg = await message.answer(
        "Broadcast boshlandi...", reply_markup=reply.admin_panel()
    )
    result = await BroadcastService(session).send_to_all(
        bot, original_chat_id, original_message_id
    )
    await status_msg.edit_text(
        f"Broadcast yakunlandi!\n"
        f"Jami: {result.total}\n"
        f"Yuborildi: {result.sent}\n"
        f"Xato: {result.failed}"
    )


@router.message(BroadcastStates.waiting_confirmation, F.text == "❌ Bekor qilish")
async def broadcast_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Broadcast bekor qilindi.", reply_markup=reply.admin_panel())
