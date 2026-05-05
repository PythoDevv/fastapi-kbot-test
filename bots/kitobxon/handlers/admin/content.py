from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, PhotoSize
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.keyboards import inline, reply
from bots.kitobxon.repositories import ContentRepository
from bots.kitobxon.states import AdminContentStates

router = Router(name="admin_content")


async def _is_admin(session: AsyncSession, telegram_id: int) -> bool:
    from bots.kitobxon.repositories import UserRepository
    user = await UserRepository(session).get_by_telegram_id(telegram_id)
    return bool(user and user.is_admin)



@router.message(F.text == "📝 Kontentlar")
async def show_content_list(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    contents = await ContentRepository(session).list_all()
    await message.answer(
        "<b>📝 Kontentlar Boshqaruvi</b>\n\nTahrirlaydigan kontentni tanlang:",
        reply_markup=inline.content_list_keyboard(contents),
    )


@router.callback_query(F.data == "ct_add")
async def start_add_content(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return
    await state.set_state(AdminContentStates.waiting_name)
    await cb.message.edit_text(
        "<b>Yangi kontent nomi</b>\n\nKontent uchun nom kiriting (masalan: <code>about</code>, <code>rules2</code>):",
        reply_markup=inline.cancel_keyboard(),
    )
    await cb.answer()


@router.callback_query(AdminContentStates.waiting_name, F.data == "cancel")
async def cancel_add_content_name(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    contents = await ContentRepository(session).list_all()
    await cb.message.edit_text(
        "<b>📝 Kontentlar Boshqaruvi</b>\n\nTahrirlaydigan kontentni tanlang:",
        reply_markup=inline.content_list_keyboard(contents),
    )
    await cb.answer()


@router.message(AdminContentStates.waiting_name)
async def receive_content_name(message: Message, state: FSMContext, session: AsyncSession) -> None:
    name = message.text.strip().lower().replace(" ", "_")
    if not name:
        await message.answer("Nom bo'sh bo'lmasin.")
        return
    existing = await ContentRepository(session).get_by_key(name)
    if existing:
        await message.answer(f"<code>{name}</code> allaqachon mavjud. Boshqa nom kiriting.")
        return
    await state.update_data(content_key=name)
    await state.set_state(AdminContentStates.waiting_text)
    await message.answer(
        f"<b>{name}</b> uchun kontent yuboring:\n"
        "• Matn xabarini yuboring\n"
        "• Yoki rasmli xabarni yuboring",
        reply_markup=inline.cancel_keyboard(),
    )


@router.callback_query(F.data.startswith("ct_manage:"))
async def show_content_manage(cb: CallbackQuery, session: AsyncSession) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return

    key = cb.data.split(":")[1]
    repo = ContentRepository(session)
    content = await repo.get_by_key(key)
    require_link = content.require_link if content else False
    status = "✅ Mavjud" if content and content.text else "⚠️ Bo'sh"

    await cb.message.edit_text(
        f"<b>📝 {key}</b>\n\nStatus: {status}\n\nNima qilmoqchisiz?",
        reply_markup=inline.content_manage_keyboard(key, require_link),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("ct_edit:"))
async def start_edit_content(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return

    key = cb.data.split(":")[1]
    await state.set_state(AdminContentStates.waiting_text)
    await state.update_data(content_key=key)

    await cb.message.edit_text(
        f"<b>{key}</b>\n\n"
        "Tayyor kontentni yuboring:\n"
        "• Matn xabarini yuboring\n"
        "• Yoki rasmli xabarni yuboring (caption qo'shilsa bo'ladi)\n"
        "• Yoki forwarded xabar yuboring",
        reply_markup=inline.cancel_keyboard(),
    )
    await cb.answer()


@router.message(AdminContentStates.waiting_text)
async def receive_content_text(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    """Receive and save content (any type: text, photo, etc.)"""
    if not message.text and not message.photo:
        await message.answer("Iltimos, matn yoki rasm yuboring.")
        return

    data = await state.get_data()
    key = data.get("content_key")
    
    # Save the message content
    repo = ContentRepository(session)
    
    if message.photo:
        # Save photo file_id
        photo = message.photo[-1]
        text_to_save = message.html_caption or ""
        await repo.upsert(key=key, text=text_to_save, image_id=photo.file_id)

        # Show preview
        await message.answer("✅ Rasm saqlandi. Quyida namuna:")
        await message.answer_photo(
            photo=photo.file_id,
            caption=text_to_save,
            parse_mode=ParseMode.HTML,
        )
    else:
        # Save text with HTML entities preserved
        text_to_save = message.html_text
        await repo.upsert(key=key, text=text_to_save)

        # Show preview
        await message.answer(
            "<b>✅ Matn saqlandi. Quyida namuna:</b>",
            parse_mode=ParseMode.HTML,
        )
        await message.answer(
            text_to_save,
            parse_mode=ParseMode.HTML,
        )
    
    await state.clear()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha (Link ko'rsatish)", callback_data=f"ct_link_yes:{key}"),
                InlineKeyboardButton(text="❌ Yo'q (Link ko'rsatmaslik)", callback_data=f"ct_link_no:{key}"),
            ]
        ]
    )
    await message.answer("Link ko'rsatilsinmi?", reply_markup=keyboard)


@router.callback_query(F.data.startswith("ct_link_yes:"))
async def handle_link_yes(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Handle link yes response"""
    key = cb.data.split(":")[1]
    repo = ContentRepository(session)
    await repo.upsert(key=key, require_link=True)
    
    await state.clear()
    await cb.message.edit_text("✅ Saqlandi! Link ko'rsatiladi.")
    await cb.answer()


@router.callback_query(F.data.startswith("ct_link_no:"))
async def handle_link_no(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Handle link no response"""
    key = cb.data.split(":")[1]
    repo = ContentRepository(session)
    await repo.upsert(key=key, require_link=False)
    
    await state.clear()
    await cb.message.edit_text("✅ Saqlandi! Link ko'rsatilmaydi.")
    await cb.answer()


@router.message(AdminContentStates.waiting_image)
async def receive_content_image(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    """Receive and save content image"""
    if message.text == "Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=reply.admin_panel())
        return

    if message.text == "o'tkazib yuborish":
        # Skip image
        await state.clear()
        await message.answer("✅ Kontent saqlandi!", reply_markup=reply.admin_panel())
        return

    if not message.photo:
        await message.answer("Iltimos, rasm yuboring yoki 'o'tkazib yuborish' tugmasini bosing.")
        return

    # Get the largest photo size
    photo: PhotoSize = message.photo[-1]
    data = await state.get_data()
    key = data.get("content_key")

    # Save image to DB
    repo = ContentRepository(session)
    await repo.upsert(key=key, image_id=photo.file_id)

    await state.clear()
    await message.answer("✅ Kontent rasm bilan saqlandi!", reply_markup=reply.admin_panel())


@router.callback_query(F.data.startswith("ct_delete:"))
async def delete_content(cb: CallbackQuery, session: AsyncSession) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return

    key = cb.data.split(":")[1]
    repo = ContentRepository(session)
    content = await repo.get_by_key(key)

    if not content:
        await cb.answer("Kontent topilmadi.", show_alert=True)
        return

    await session.delete(content)
    await session.flush()

    await cb.answer(f"✅ {key} o'chirildi.", show_alert=True)
    contents = await repo.list_all()
    await cb.message.edit_text(
        "<b>📝 Kontentlar Boshqaruvi</b>\n\nTahrirlaydigan kontentni tanlang:",
        reply_markup=inline.content_list_keyboard(contents),
    )


@router.callback_query(F.data == "cancel")
async def cancel_edit_content(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    contents = await ContentRepository(session).list_all()
    await cb.message.edit_text(
        "<b>📝 Kontentlar Boshqaruvi</b>\n\nTahrirlaydigan kontentni tanlang:",
        reply_markup=inline.content_list_keyboard(contents),
    )
    await cb.answer("Bekor qilindi.")


@router.callback_query(F.data.startswith("ct_link:"))
async def toggle_require_link(cb: CallbackQuery, session: AsyncSession) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return

    key = cb.data.split(":")[1]
    repo = ContentRepository(session)
    content = await repo.get_by_key(key)
    new_require_link = not (content.require_link if content else False)
    await repo.upsert(key=key, require_link=new_require_link)
    await cb.message.edit_reply_markup(
        reply_markup=inline.content_manage_keyboard(key, new_require_link)
    )
    link_status = "✅ Yoqildi" if new_require_link else "❌ O'chirildi"
    await cb.answer(f"Link: {link_status}", show_alert=True)
