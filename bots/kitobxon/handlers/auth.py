from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.keyboards import inline, reply
from bots.kitobxon.repositories import QuizRepository, UserRepository
from bots.kitobxon.services import AuthService, SubsService
from bots.kitobxon.states import AuthStates
from core.logging import get_logger

logger = get_logger(__name__)
router = Router(name="auth")


@router.message(AuthStates.awaiting_name)
async def handle_name_input(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    text = (message.text or "").strip()
    if text == "Bekor qilish":
        await state.clear()
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(message.from_user.id)
        if user and user.is_admin:
            await message.answer("Admin panel:", reply_markup=reply.admin_panel())
        else:
            await message.answer("Asosiy menyu:", reply_markup=reply.main_menu())
        return

    if len(text) < 3:
        await message.answer("Iltimos, to'liq ism familiyangizni kiriting (kamida 3 harf):")
        return

    auth = AuthService(session)
    await auth.set_name(message.from_user.id, text)

    # Check if phone number is required
    quiz_repo = QuizRepository(session)
    settings = await quiz_repo.get_settings()
    require_phone = settings.require_phone_number if settings else False

    if require_phone:
        await state.set_state(AuthStates.awaiting_phone)
        await message.answer(
            "Telefon raqamingizni yuboring:",
            reply_markup=reply.phone_request(),
        )
    else:
        # Skip phone and finish registration
        await _finish_registration(message, state, session, bot, phone="")


@router.message(AuthStates.awaiting_phone, F.contact)
async def handle_phone_contact(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    phone = message.contact.phone_number
    await _finish_registration(message, state, session, bot, phone)


@router.message(AuthStates.awaiting_phone, F.text)
async def handle_phone_text(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    phone = (message.text or "").strip()
    if not phone.startswith("+") or len(phone) < 9:
        await message.answer("Iltimos, telefon raqamingizni to'g'ri kiriting (+998...):")
        return
    await _finish_registration(message, state, session, bot, phone)


async def _finish_registration(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    phone: str,
) -> None:
    auth = AuthService(session)
    await auth.set_phone(message.from_user.id, phone)
    await auth.mark_registered(message.from_user.id)
    await state.clear()

    subs = SubsService(session)
    user = await auth.touch_user(message.from_user.id, None, None)
    status = await subs.check_user(bot, message.from_user.id, user.user.id)

    if not status.all_subscribed:
        await message.answer(
            "Ro'yxatdan o'tdingiz! Botdan foydalanish uchun kanallarga obuna bo'ling:",
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
            f"{message.from_user.full_name or message.from_user.first_name or message.from_user.username} "
            "sizning referalingiz orqali ro'yxatdan o'tdi.\n"
            f"Referallar soni: <b>{referrer_referrals}</b>",
        )
    await message.answer("Tabriklaymiz! Ro'yxatdan o'tdingiz.", reply_markup=reply.main_menu())


@router.message(AuthStates.changing_name)
async def handle_name_change(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    text = (message.text or "").strip()
    if text == "Bekor qilish":
        await state.clear()
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(message.from_user.id)
        if user and user.is_admin:
            await message.answer("Admin panel:", reply_markup=reply.admin_panel())
        else:
            await message.answer("Asosiy menyu:", reply_markup=reply.main_menu())
        return

    if len(text) < 3:
        await message.answer("Iltimos, to'liq ism familiyangizni kiriting (kamida 3 harf):")
        return
    await AuthService(session).set_name(message.from_user.id, text)
    await state.clear()
    await message.answer(f"Ismingiz o'zgartirildi: <b>{text}</b>", reply_markup=reply.main_menu())
