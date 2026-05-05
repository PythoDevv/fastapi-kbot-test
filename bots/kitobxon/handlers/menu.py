import os

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.keyboards import reply
from bots.kitobxon.repositories import ContentRepository, UserRepository
from bots.kitobxon.services import AuthService, SubsService
from bots.kitobxon.states import AuthStates
from core.config import settings

router = Router(name="menu")

BASE_URL = settings.BASE_WEBHOOK_URL


@router.message(F.text == "🏠 Asosiy menyu")
@router.message(F.text == "Bekor qilish")
async def back_to_menu(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await state.clear()
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(message.from_user.id)
    if user and user.is_admin:
        await message.answer("Admin panel:", reply_markup=reply.admin_panel())
        return
    await message.answer("Asosiy menyu:", reply_markup=reply.main_menu())


@router.message(F.text == "Ismni o'zgartirish ✏️")
async def change_name(message: Message, state: FSMContext) -> None:
    await state.set_state(AuthStates.changing_name)
    await message.answer(
        "Yangi ism familiyangizni kiriting:", reply_markup=reply.cancel_only()
    )


@router.message(F.text == "💠 Do'stlarni taklif qilish")
async def referral_link(message: Message, session: AsyncSession) -> None:
    bot_username = (await message.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={message.from_user.id}"
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(message.from_user.id)
    count = user.referrals_count if user else 0

    # Get custom referral content if exists
    content_repo = ContentRepository(session)
    content = await content_repo.get_by_key("referral")

    # Build message
    text_parts = []

    # Add custom content text if exists
    if content and content.text:
        text_parts.append(content.text)

    # Add referral link if content requires it or if no content exists
    should_show_link = (not content) or content.require_link
    if should_show_link:
        text_parts.append(f"Referal havolangiz:\n{link}")

    # Add referral count
    text_parts.append(f"\nSiz taklif qilgan do'stlar soni: <b>{count}</b>")

    final_text = "\n\n".join(text_parts)

    # Build button when link is shown
    reply_markup = None
    if should_show_link:
        reply_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔗 Referal havola", url=link)]
            ]
        )

    # Send with or without photo based on content.image_id
    if content and content.image_id:
        await message.answer_photo(
            photo=content.image_id,
            caption=final_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )
    else:
        await message.answer(final_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


@router.message(F.text == "📝 Tanlov shartlari")
async def show_nizom(message: Message, session: AsyncSession) -> None:
    repo = ContentRepository(session)
    content = await repo.get_by_key("nizom")
    if not content:
        await message.answer("Tanlov shartlari hali kiritilmagan.")
        return
    if content.image_id:
        await message.answer_photo(
            photo=content.image_id,
            caption=content.text or "",
            parse_mode=ParseMode.HTML,
        )
    else:
        await message.answer(
            content.text or "Tanlov shartlari.",
            parse_mode=ParseMode.HTML,
        )


@router.message(F.text == "Tanlov kitoblari 📚")
async def show_books(message: Message, session: AsyncSession) -> None:
    from bots.kitobxon.repositories import BookRepository
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    repo = BookRepository(session)
    books = await repo.list_all()
    if not books:
        await message.answer("Hozircha kitoblar yo'q.")
        return
    buttons = [
        [InlineKeyboardButton(text=b.button_text or b.title or "Kitob", url=b.button_url)]
        for b in books
        if b.button_url
    ]
    await message.answer(
        "Tanlov kitoblari:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None,
    )


@router.message(F.text == "Viktorina sovg'alari 🎁")
async def show_prizes(message: Message, session: AsyncSession) -> None:
    repo = ContentRepository(session)
    content = await repo.get_by_key("prizes")
    if not content:
        await message.answer("Sovg'alar haqida ma'lumot hali kiritilmagan.")
        return
    if content.image_id:
        await message.answer_photo(
            photo=content.image_id,
            caption=content.text or "",
            parse_mode=ParseMode.HTML,
        )
    else:
        await message.answer(
            content.text or "Sovg'alar haqida ma'lumot.",
            parse_mode=ParseMode.HTML,
        )
