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


def _subscription_prompt_text(has_missing: bool) -> str:
    if has_missing:
        return "Quyidagi kanallarga hali obuna bo'lmadingiz:"
    return "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:"


async def _continue_after_subscription(
    message: Message,
    state: FSMContext,
    is_registered: bool,
) -> None:
    if is_registered:
        await message.answer("Asosiy menyu:", reply_markup=reply.main_menu())
        return

    await state.set_state(AuthStates.awaiting_name)
    await message.answer(
        "Assalomu alaykum! Ismingiz va familiyangizni kiriting:",
        reply_markup=reply.REMOVE,
    )


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
            _subscription_prompt_text(False),
            reply_markup=inline.subscription_keyboard(
                status.missing_channels, status.missing_zayafka
            ),
        )
        return

    referral_result = await auth.award_referral_bonus_if_eligible(message.from_user.id)
    if referral_result:
        referrer_id, referrer_referrals = referral_result
        await bot.send_message(
            referrer_id,
            f"{result.user.fio or result.user.username or message.from_user.first_name} "
            "sizning referalingiz orqali ro'yxatdan o'tdi.\n"
            f"Sizdagi referallar soni: <b>{referrer_referrals}</b>",
        )
    await _continue_after_subscription(message, state, result.user.is_registered)


@router.callback_query(F.data == "check_subscription")
async def check_subscription(
    cb: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot
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
        referral_result = await auth.award_referral_bonus_if_eligible(cb.from_user.id)
        if referral_result:
            referrer_id, referrer_referrals = referral_result
            await bot.send_message(
                referrer_id,
                f"{result.user.fio or result.user.username or cb.from_user.first_name} "
                "sizning referalingiz orqali ro'yxatdan o'tdi.\n"
                f"Sizdagi referallar soni: <b>{referrer_referrals}</b>",
            )
        await _continue_after_subscription(
            cb.message,
            state,
            result.user.is_registered,
        )
    else:
        await cb.answer()
        await cb.message.edit_text(
            _subscription_prompt_text(True),
            reply_markup=inline.subscription_keyboard(
                status.missing_channels, status.missing_zayafka
            ),
        )
