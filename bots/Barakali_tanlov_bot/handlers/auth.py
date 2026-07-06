from aiogram import Bot, F, Router
from aiogram.filters import Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.Barakali_tanlov_bot.keyboards import inline, reply
from bots.Barakali_tanlov_bot.repositories import QuizRepository, UserRepository
from bots.Barakali_tanlov_bot.services import AuthService, SubsService
from bots.Barakali_tanlov_bot.states import AuthStates
from core.logging import get_logger

logger = get_logger(__name__)
router = Router(name="auth")

_NON_NAME_TEXTS = {
    "Bekor qilish",
    "📱 Telefon raqamni yuborish",
    "💠 Do'stlarni taklif qilish",
    "Test savollarini ishlash 🧑‍💻",
    "🌟 Natijalar",
    "📝 Tanlov shartlari",
    "Tanlov kitoblari 📚",
    "Viktorina sovg'alari 🎁",
    "Oila nomini o'zgartirish ✏️",
    "🏠 Asosiy menyu",
    "🔙 Admin panel",
}


class AwaitingNameFallback(Filter):
    async def __call__(
        self,
        message: Message,
        state: FSMContext,
        session: AsyncSession,
    ) -> bool:
        text = (message.text or "").strip()
        if not text or text.startswith("/") or text in _NON_NAME_TEXTS:
            return False
        if await state.get_state() is not None:
            return False
        user = await UserRepository(session).get_by_telegram_id(message.from_user.id)
        return bool(user and not user.is_registered and not user.mobile_number)


async def _handle_name_submission(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
) -> None:
    text = (message.text or "").strip()
    if text == "Bekor qilish":
        await state.clear()
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(message.from_user.id)
        if user and user.is_admin:
            await message.answer("Asosiy menyu:", reply_markup=reply.main_menu())
        else:
            await message.answer("Asosiy menyu:", reply_markup=reply.main_menu())
        return

    if len(text) < 3:
        await message.answer("Iltimos, Ismingiz va familiyangizni kiriting\n\n Misol uchun : Alijonov Alisher")Z
        return

    auth = AuthService(session)
    await auth.set_name(message.from_user.id, text)

    quiz_repo = QuizRepository(session)
    settings = await quiz_repo.get_settings()
    require_phone = settings.require_phone_number if settings else False

    if require_phone:
        await state.set_state(AuthStates.awaiting_phone)
        await message.answer(
            "Telefon raqamingizni yuboring:",
            reply_markup=reply.phone_request(),
        )
        return

    await _finish_registration(message, state, session, bot, phone="")


@router.message(AuthStates.awaiting_name)
async def handle_name_input(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    await _handle_name_submission(message, state, session, bot)


@router.message(AwaitingNameFallback())
async def handle_name_input_without_state(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    await _handle_name_submission(message, state, session, bot)


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

    award = await auth.award_referral_bonus_if_eligible(message.from_user.id)
    if award:
        await bot.send_message(
            award.referrer_telegram_id,
            f"{award.new_user_name} "
            "sizning referalingiz orqali ro'yxatdan o'tdi.\n"
            f"Referallar soni: <b>{award.referrals_count}</b>",
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
        await message.answer("Iltimos, Ismingiz va familiyangizni kiriting\n\n Misol uchun : Alijonov Alisher")
        return
    await AuthService(session).set_name(message.from_user.id, text)
    await state.clear()
    await message.answer(f"Ismingiz o'zgartirildi: <b>{text}</b>", reply_markup=reply.main_menu())
