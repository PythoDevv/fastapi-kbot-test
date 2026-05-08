from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.Kitobmillatbot.keyboards import inline, reply
from bots.Kitobmillatbot.models import User
from bots.Kitobmillatbot.repositories import QuizRepository
from bots.Kitobmillatbot.services import AuthService, SubsService
from bots.Kitobmillatbot.states import AuthStates
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
    session: AsyncSession,
    user: User,
) -> bool:
    if user.is_registered:
        await message.answer("Asosiy menyu:", reply_markup=reply.main_menu())
        return True

    settings = await QuizRepository(session).get_settings()
    require_phone = settings.require_phone_number if settings else False
    has_name = user.step >= 1 and bool((user.fio or "").strip())

    if has_name:
        has_phone = bool((user.mobile_number or "").strip())
        if require_phone and not has_phone:
            await state.set_state(AuthStates.awaiting_phone)
            await message.answer(
                "Telefon raqamingizni yuboring:",
                reply_markup=reply.phone_request(),
            )
            return False

        await AuthService(session).mark_registered(user.telegram_id)
        await state.clear()
        await message.answer("Tabriklaymiz! Ro'yxatdan o'tdingiz.", reply_markup=reply.main_menu())
        return True

    await state.set_state(AuthStates.awaiting_name)
    await message.answer(
        "Assalomu alaykum! Ismingiz va familiyangizni kiriting:",
        reply_markup=reply.REMOVE,
    )
    return False


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

    # Parse referral and persist to DB immediately so it survives any
    # subsequent state.clear() or /start re-invocation without referral arg.
    args = message.text.split(maxsplit=1)
    if len(args) > 1 and not result.user.is_registered and not result.user.referred_by:
        try:
            referrer_id = int(args[1])
        except ValueError:
            referrer_id = None
        if referrer_id and referrer_id != message.from_user.id:
            await auth.apply_referral(result.user, referrer_id)

    # Adminlar uchun obuna tekshiruvi yo'q
    if not result.user.is_admin:
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

    is_registered = await _continue_after_subscription(
        message,
        state,
        session,
        result.user,
    )
    if is_registered:
        referral_result = await auth.award_referral_bonus_if_eligible(message.from_user.id)
        if referral_result:
            referrer_id, referrer_referrals = referral_result
            await bot.send_message(
                referrer_id,
                f"{result.user.fio or result.user.username or message.from_user.first_name} "
                "sizning referalingiz orqali ro'yxatdan o'tdi.\n"
                f"Referallar soni: <b>{referrer_referrals}</b>",
            )


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
    if result.user.is_admin:
        await cb.message.delete()
        await _continue_after_subscription(
            cb.message,
            state,
            session,
            result.user,
        )
        await cb.answer()
        return

    subs = SubsService(session)
    status = await subs.check_user(bot, cb.from_user.id, result.user.id)

    if status.all_subscribed:
        await cb.message.delete()
        is_registered = await _continue_after_subscription(
            cb.message,
            state,
            session,
            result.user,
        )
        if is_registered:
            referral_result = await auth.award_referral_bonus_if_eligible(cb.from_user.id)
            if referral_result:
                referrer_id, referrer_referrals = referral_result
                await bot.send_message(
                    referrer_id,
                    f"{result.user.fio or result.user.username or cb.from_user.first_name} "
                    "sizning referalingiz orqali ro'yxatdan o'tdi.\n"
                    f"Referallar soni: <b>{referrer_referrals}</b>",
                )
        await cb.answer()
    else:
        text = _subscription_prompt_text(True)
        markup = inline.subscription_keyboard(
            status.missing_channels, status.missing_zayafka
        )
        try:
            await cb.message.edit_text(text, reply_markup=markup)
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                raise
        await cb.answer("Hali barcha kanallarga obuna bo'lmadingiz.")
