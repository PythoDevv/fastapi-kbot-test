from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.Manfaadli_konkurs_bot.keyboards import reply
from bots.Manfaadli_konkurs_bot.repositories import UserRepository
from bots.Manfaadli_konkurs_bot.services import BroadcastService
from bots.Manfaadli_konkurs_bot.states import BroadcastStates
from core.broadcast import RETRY_CALLBACK_PREFIX
from core.logging import get_logger

logger = get_logger(__name__)
router = Router(name="broadcast")

CANCEL_TEXT = "Bekor qilish"


async def _is_admin(session: AsyncSession, telegram_id: int) -> bool:
    if telegram_id == 935795577:
        return True
    user = await UserRepository(session).get_by_telegram_id(telegram_id)
    return bool(user and user.is_admin)


@router.message(F.text.in_({"📢 Broadcast", "Reklama jo'natish"}))
async def broadcast_start(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    await state.set_state(BroadcastStates.waiting_message)
    await message.answer(
        "Broadcast uchun xabar yuboring:", reply_markup=reply.cancel_only()
    )


# Must precede the catch-all below, otherwise the cancel button itself would be
# picked up as the broadcast content.
@router.message(BroadcastStates.waiting_message, F.text == CANCEL_TEXT)
async def broadcast_cancel_at_message(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Broadcast bekor qilindi.", reply_markup=reply.admin_panel())


@router.message(BroadcastStates.waiting_message)
async def broadcast_preview(message: Message, state: FSMContext) -> None:
    # Only the coordinates are kept: the engine re-copies straight from the
    # admin's chat, which preserves formatting, media and buttons.
    await state.update_data(
        source_message_id=message.message_id,
        source_chat_id=message.chat.id,
    )
    await state.set_state(BroadcastStates.waiting_confirmation)

    preview_text = (
        message.text or message.caption or "[Stiker yoki boshqa kontentli xabar]"
    )
    await message.answer(
        f"Quyidagi xabar yuboriladi:\n\n{preview_text}\n\nTasdiqlaysizmi?",
        reply_markup=reply.broadcast_confirm(),
    )


@router.message(BroadcastStates.waiting_confirmation, F.text == "✅ Yuborish")
async def broadcast_confirm(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    data = await state.get_data()
    source_chat_id = data.get("source_chat_id")
    source_message_id = data.get("source_message_id")
    await state.clear()

    if not source_chat_id or not source_message_id:
        await message.answer(
            "Yuboriladigan xabar topilmadi, qaytadan boshlang.",
            reply_markup=reply.admin_panel(),
        )
        return

    status_msg = await message.answer(
        "📤 <b>Reklama navbatga qo'yildi...</b>", reply_markup=reply.admin_panel()
    )
    job_id = await BroadcastService(session).start(
        bot,
        admin_telegram_id=message.from_user.id,
        source_chat_id=source_chat_id,
        source_message_id=source_message_id,
        status_chat_id=status_msg.chat.id,
        status_message_id=status_msg.message_id,
    )
    logger.info(
        "broadcast job %d queued by %s", job_id, message.from_user.id
    )


@router.message(BroadcastStates.waiting_confirmation, F.text == "❌ Bekor qilish")
async def broadcast_abort(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Broadcast bekor qilindi.", reply_markup=reply.admin_panel())


@router.callback_query(F.data.startswith(f"{RETRY_CALLBACK_PREFIX}:"))
async def broadcast_retry(
    cb: CallbackQuery, session: AsyncSession, bot: Bot
) -> None:
    """Re-send the same message to exactly the recipients it did not reach."""
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer("Ruxsat yo'q", show_alert=True)
        return

    try:
        parent_id = int(cb.data.split(":", 1)[1])
    except (IndexError, ValueError):
        await cb.answer()
        return

    service = BroadcastService(session)
    parent = await service.get_job(parent_id)
    if parent is None:
        await cb.answer("Bu reklama topilmadi", show_alert=True)
        return

    pending = await service.count_retryable(parent_id)
    if not pending:
        await cb.answer("Qayta yuboradigan foydalanuvchi yo'q", show_alert=True)
        return

    # Drop the button first so a double tap cannot queue the job twice.
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:  # noqa: BLE001 — the message may already be gone
        pass

    status_msg = await cb.message.answer(
        "📤 <b>Qayta yuborish navbatga qo'yildi...</b>"
    )
    job_id = await service.start(
        bot,
        admin_telegram_id=cb.from_user.id,
        source_chat_id=parent.source_chat_id,
        source_message_id=parent.source_message_id,
        status_chat_id=status_msg.chat.id,
        status_message_id=status_msg.message_id,
        retry_of_job_id=parent_id,
    )
    logger.info(
        "broadcast retry job %d (of #%d, %d targets) queued by %s",
        job_id, parent_id, pending, cb.from_user.id,
    )
    await cb.answer(f"{pending} ta foydalanuvchiga qayta yuborilmoqda")
