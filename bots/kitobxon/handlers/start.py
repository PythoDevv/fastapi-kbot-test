from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.keyboards import inline, reply
from bots.kitobxon.services import AuthService, SubsService
from bots.kitobxon.states import AuthStates
from core.logging import get_logger

logger = get_logger(__name__)
router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    await state.clear()

    auth = AuthService(session)
    result = await auth.touch_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )

    # Parse referral
    args = message.text.split(maxsplit=1)
    if len(args) > 1 and result.is_new:
        try:
            referrer_id = int(args[1])
            await auth.apply_referral(result.user, referrer_id)
        except (ValueError, Exception):
            pass

    # Check subscription first (for both new and registered users)
    subs = SubsService(session)
    status = await subs.check_user(bot, message.from_user.id, result.user.id)
    if not status.all_subscribed:
        await message.answer(
            "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=inline.subscription_keyboard(
                status.missing_channels, status.missing_zayafka
            ),
        )
        return

    if result.user.is_registered:
        await message.answer("Asosiy menyu:", reply_markup=reply.main_menu())
        return

    # New user — collect name (no cancel allowed, subscriptions already checked)
    await state.set_state(AuthStates.awaiting_name)
    await message.answer(
        "Assalomu alaykum! Ismingiz va familiyangizni kiriting:",
        reply_markup=reply.REMOVE,
    )


@router.callback_query(F.data == "check_subscription")
async def check_subscription(
    cb: CallbackQuery, session: AsyncSession, bot: Bot
) -> None:
    auth = AuthService(session)
    result = await auth.touch_user(
        telegram_id=cb.from_user.id,
        username=cb.from_user.username,
        first_name=cb.from_user.first_name,
    )
    subs = SubsService(session)
    status = await subs.check_user(bot, cb.from_user.id, result.user.id)

    if status.all_subscribed:
        await cb.message.delete()
        await cb.message.answer("Asosiy menyu:", reply_markup=reply.main_menu())
    else:
        await cb.answer("Hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)
        await cb.message.edit_reply_markup(
            reply_markup=inline.subscription_keyboard(
                status.missing_channels, status.missing_zayafka
            )
        )
