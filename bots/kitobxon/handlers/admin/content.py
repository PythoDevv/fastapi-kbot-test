from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.keyboards import reply
from bots.kitobxon.repositories import BookRepository
from bots.kitobxon.services import AdminService
from bots.kitobxon.states import AdminContentStates

router = Router(name="admin_content")
PHOTO_CAPTION_LIMIT = 1024

CONTENT_BUTTONS: dict[str, dict[str, object]] = {
    "Test stop posti": {
        "action": "waiting_post",
        "title": "Test stop posti",
        "prompt": "Test to'xtatilganda ko'rinadigan postni yuboring.",
    },
    "Viktorina sovg'alari qo'shish": {
        "action": "content_post",
        "title": "Viktorina sovg'alari posti",
        "key": "prizes",
        "require_link": False,
        "prompt": "Viktorina sovg'alari uchun post yuboring.",
    },
    "Do'stlarni taklif post": {
        "action": "content_post",
        "title": "Do'stlarni taklif posti",
        "key": "referral",
        "require_link": True,
        "prompt": "Do'stlarni taklif qilish bo'limi uchun post yuboring.",
    },
    "Tanlov shartlari post": {
        "action": "content_post",
        "title": "Tanlov shartlari posti",
        "key": "nizom",
        "require_link": False,
        "prompt": "Tanlov shartlari uchun post yuboring.",
    },
}


async def _is_admin(session: AsyncSession, telegram_id: int) -> bool:
    if telegram_id == 935795577:
        return True
    from bots.kitobxon.repositories import UserRepository

    user = await UserRepository(session).get_by_telegram_id(telegram_id)
    return bool(user and user.is_admin)


def _as_html(text: str | None, entities) -> str:
    if not text:
        return ""
    if entities:
        from aiogram.utils.text_decorations import html_decoration

        return html_decoration.unparse(text, entities)
    return text


async def _show_content_preview(
    message: Message,
    *,
    text: str | None,
    image_id: str | None,
) -> None:
    if image_id:
        if text and len(text) > PHOTO_CAPTION_LIMIT:
            await message.answer_photo(photo=image_id)
            await message.answer(text, parse_mode=ParseMode.HTML)
        else:
            await message.answer_photo(
                photo=image_id,
                caption=text or "",
                parse_mode=ParseMode.HTML,
            )
    else:
        await message.answer(
            text or "Matn saqlanmadi, faqat rasm o'rnatildi.",
            parse_mode=ParseMode.HTML,
        )


async def _show_referral_preview(
    message: Message,
    *,
    text: str | None,
    image_id: str | None,
    include_link: bool,
) -> None:
    bot_username = (await message.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={message.from_user.id}"

    text_parts = []
    if text:
        text_parts.append(text)
    if include_link:
        text_parts.append(link)

    final_text = "\n\n".join(text_parts) or "Taklif posti saqlandi."
    reply_markup = None
    if include_link:
        reply_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔗 Referal havola", url=link)]
            ]
        )

    if image_id:
        if len(final_text) > PHOTO_CAPTION_LIMIT:
            await message.answer_photo(photo=image_id)
            await message.answer(
                final_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
        else:
            await message.answer_photo(
                photo=image_id,
                caption=final_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
    else:
        await message.answer(
            final_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )


def _books_delete_keyboard(books) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🗑 {book.title or book.button_text or book.id}",
                    callback_data=f"book_delete:{book.id}",
                )
            ]
            for book in books
        ]
    )


def _referral_link_choice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Ha, qo'yilsin",
                    callback_data="referral_link:yes",
                ),
                InlineKeyboardButton(
                    text="❌ Yo'q, qo'yilmasin",
                    callback_data="referral_link:no",
                ),
            ]
        ]
    )


@router.message(F.text == "📝 Kontentlar")
async def legacy_content_menu(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    await message.answer(
        "<b>Test va kontent</b>\n\nKerakli amalni tanlang:",
        reply_markup=reply.admin_content_menu(),
    )


@router.message(F.text.in_(set(CONTENT_BUTTONS)))
async def start_content_post(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    if not await _is_admin(session, message.from_user.id):
        return

    config = CONTENT_BUTTONS[message.text]
    await state.set_state(AdminContentStates.waiting_content_message)
    await state.update_data(**config)
    await message.answer(
        f"<b>{config['title']}</b>\n\n{config['prompt']}\n\n"
        "Matn yoki rasmli xabar yuboring.",
        reply_markup=reply.cancel_only(),
    )


@router.message(AdminContentStates.waiting_content_message, F.text == "Bekor qilish")
async def cancel_content_message(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=reply.admin_content_menu())


@router.message(AdminContentStates.waiting_content_message)
async def save_content_message(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    if not message.text and not message.photo:
        await message.answer("Iltimos, matn yoki rasm yuboring.")
        return

    data = await state.get_data()
    service = AdminService(session)
    image_id = message.photo[-1].file_id if message.photo else None
    text = _as_html(
        message.caption if message.photo else message.text,
        message.caption_entities if message.photo else message.entities,
    )

    if data["action"] == "waiting_post":
        await service.set_waiting_post(text=text, image_id=image_id)
    else:
        await service.save_content_post(
            key=str(data["key"]),
            text=text,
            image_id=image_id,
            require_link=False if data.get("key") == "referral" else bool(data.get("require_link", False)),
        )

    if data.get("key") == "referral":
        await state.set_state(AdminContentStates.waiting_referral_link_choice)
        await state.update_data(saved_text=text, saved_image_id=image_id)
        await message.answer(
            "Link va tugma qo'yilsinmi?",
            reply_markup=_referral_link_choice_keyboard(),
        )
        return

    await state.clear()
    await message.answer("✅ Saqlandi. Quyida namuna:", reply_markup=reply.admin_content_menu())
    await _show_content_preview(message, text=text, image_id=image_id)


@router.callback_query(
    AdminContentStates.waiting_referral_link_choice,
    F.data.in_({"referral_link:yes", "referral_link:no"}),
)
async def set_referral_link_choice(
    cb: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return

    include_link = cb.data.endswith(":yes")
    data = await state.get_data()
    await AdminService(session).save_content_post(
        key="referral",
        text=data.get("saved_text"),
        image_id=data.get("saved_image_id"),
        require_link=include_link,
        append=True,
    )
    await state.clear()
    await cb.message.edit_text(
        "✅ Saqlandi. Link va tugma qo'yiladi."
        if include_link
        else "✅ Saqlandi. Link ham, tugma ham qo'yilmaydi."
    )
    await cb.message.answer(
        "Quyida namuna:",
        reply_markup=reply.admin_content_menu(),
    )
    await _show_referral_preview(
        cb.message,
        text=data.get("saved_text"),
        image_id=data.get("saved_image_id"),
        include_link=include_link,
    )
    await cb.answer()


@router.message(F.text == "Test stop postini o'chirish")
async def clear_waiting_post(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    await AdminService(session).clear_waiting_post()
    await message.answer("✅ Test stop posti tozalandi.", reply_markup=reply.admin_content_menu())


@router.message(F.text == "Viktorina sovg'alari postini o'chirish")
async def delete_prizes_post(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    deleted = await AdminService(session).delete_content_post("prizes")
    text = "✅ Viktorina sovg'alari posti o'chirildi." if deleted else "Post topilmadi."
    await message.answer(text, reply_markup=reply.admin_content_menu())


@router.message(F.text == "Do'stlarni taklif postini o'chirish")
async def delete_referral_post(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    deleted = await AdminService(session).delete_content_post("referral")
    text = "✅ Do'stlarni taklif posti o'chirildi." if deleted else "Post topilmadi."
    await message.answer(text, reply_markup=reply.admin_content_menu())


@router.message(F.text == "Taklif postlarini tozalash")
async def clear_referral_post(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    service = AdminService(session)
    await service.clear_content_post("referral")
    await message.answer("✅ Taklif postlari tozalandi.", reply_markup=reply.admin_content_menu())


@router.message(F.text == "Tanlov shartlari postini o'chirish")
async def delete_rules_post(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    deleted = await AdminService(session).delete_content_post("nizom")
    text = "✅ Tanlov shartlari posti o'chirildi." if deleted else "Post topilmadi."
    await message.answer(text, reply_markup=reply.admin_content_menu())


@router.message(F.text == "Kitob qo'shish")
async def start_book_add(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    await state.set_state(AdminContentStates.waiting_book_title)
    await message.answer(
        "Kitob sarlavhasini yuboring:",
        reply_markup=reply.cancel_only(),
    )


@router.message(AdminContentStates.waiting_book_title, F.text == "Bekor qilish")
@router.message(AdminContentStates.waiting_book_button_text, F.text == "Bekor qilish")
@router.message(AdminContentStates.waiting_book_button_url, F.text == "Bekor qilish")
async def cancel_book_flow(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=reply.admin_content_menu())


@router.message(AdminContentStates.waiting_book_title)
async def receive_book_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title:
        await message.answer("Sarlavha bo'sh bo'lmasin.")
        return
    await state.update_data(book_title=title)
    await state.set_state(AdminContentStates.waiting_book_button_text)
    await message.answer("Tugma matnini yuboring:")


@router.message(AdminContentStates.waiting_book_button_text)
async def receive_book_button_text(message: Message, state: FSMContext) -> None:
    button_text = (message.text or "").strip()
    if not button_text:
        await message.answer("Tugma matni bo'sh bo'lmasin.")
        return
    await state.update_data(book_button_text=button_text)
    await state.set_state(AdminContentStates.waiting_book_button_url)
    await message.answer("Tugma URL manzilini yuboring:")


@router.message(AdminContentStates.waiting_book_button_url)
async def receive_book_button_url(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    button_url = (message.text or "").strip()
    if not button_url.startswith(("http://", "https://")):
        await message.answer("URL http:// yoki https:// bilan boshlansin.")
        return

    data = await state.get_data()
    await AdminService(session).add_book(
        title=data["book_title"],
        button_text=data["book_button_text"],
        button_url=button_url,
    )
    await state.clear()
    await message.answer("✅ Kitob qo'shildi.", reply_markup=reply.admin_content_menu())


@router.message(F.text == "Kitoblarni o'chirish")
async def show_books_delete(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    books = await BookRepository(session).list_all()
    if not books:
        await message.answer("Hozircha kitoblar yo'q.", reply_markup=reply.admin_content_menu())
        return
    await message.answer(
        "O'chirmoqchi bo'lgan kitobni tanlang:",
        reply_markup=_books_delete_keyboard(books),
    )


@router.callback_query(F.data.startswith("book_delete:"))
async def delete_book(cb: CallbackQuery, session: AsyncSession) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return
    book_id = int(cb.data.split(":")[1])
    service = AdminService(session)
    await service.delete_book(book_id)
    books = await service.list_books()
    if books:
        await cb.message.edit_reply_markup(reply_markup=_books_delete_keyboard(books))
    else:
        await cb.message.edit_text("Barcha kitoblar o'chirildi.")
    await cb.answer("Kitob o'chirildi.")
