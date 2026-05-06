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
PHOTO_CAPTION_LIMIT = 1024


async def _answer_photo_with_safe_text(
    message: Message,
    *,
    photo: str,
    text: str,
    reply_markup=None,
) -> None:
    if len(text) > PHOTO_CAPTION_LIMIT:
        await message.answer_photo(photo=photo)
        await message.answer(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )
        return

    await message.answer_photo(
        photo=photo,
        caption=text,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup,
    )


@router.message(F.text == "🏠 Asosiy menyu")
@router.message(F.text == "Bekor qilish")
async def back_to_menu(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await state.clear()
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

    content_repo = ContentRepository(session)
    contents = await content_repo.list_by_key_group("referral")
    if not contents:
        reply_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔗 Referal havola", url=link)]
            ]
        )
        await message.answer(link, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        return

    for content in contents:
        text_parts = []
        if content.text:
            text_parts.append(content.text)
        if content.require_link:
            text_parts.append(link)

        final_text = "\n\n".join(text_parts) or link
        reply_markup = None
        if content.require_link:
            reply_markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔗 Referal havola", url=link)]
                ]
            )

        if content.image_id:
            await _answer_photo_with_safe_text(
                message,
                photo=content.image_id,
                text=final_text,
                reply_markup=reply_markup,
            )
        else:
            await message.answer(
                final_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )


@router.message(F.text == "📝 Tanlov shartlari")
async def show_nizom(message: Message, session: AsyncSession) -> None:
    repo = ContentRepository(session)
    content = await repo.get_by_key("nizom")
    if not content:
        await message.answer("Tanlov shartlari hali kiritilmagan.")
        return
    if content.image_id:
        await _answer_photo_with_safe_text(
            message,
            photo=content.image_id,
            text=content.text or "",
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

    book_lines = []
    for index, book in enumerate(books, start=1):
        title = (book.title or "").strip()
        button_text = (book.button_text or "").strip()
        if title:
            book_lines.append(f"{index}. {title}")
        elif button_text:
            book_lines.append(f"{index}. {button_text}")

    buttons = [
        [InlineKeyboardButton(text=b.button_text or b.title or "Kitob", url=b.button_url)]
        for b in books
        if b.button_url
    ]
    text = "Tanlov kitoblari:"
    if book_lines:
        text = f"{text}\n\n" + "\n\n".join(book_lines)

    await message.answer(
        text,
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
        await _answer_photo_with_safe_text(
            message,
            photo=content.image_id,
            text=content.text or "",
        )
    else:
        await message.answer(
            content.text or "Sovg'alar haqida ma'lumot.",
            parse_mode=ParseMode.HTML,
        )
