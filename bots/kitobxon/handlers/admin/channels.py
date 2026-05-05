from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.keyboards import reply
from bots.kitobxon.services import AdminService
from bots.kitobxon.states import AdminChannelStates, AdminZayafkaStates

router = Router(name="admin_channels")


async def _is_admin(session: AsyncSession, telegram_id: int) -> bool:
    from bots.kitobxon.repositories import UserRepository
    user = await UserRepository(session).get_by_telegram_id(telegram_id)
    return bool(user and user.is_admin)


# ---------------------------------------------------------------
# Mandatory channels
# ---------------------------------------------------------------
def _channel_delete_keyboard(channels) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🗑 {ch.channel_name}",
                    callback_data=f"ch_delete:{ch.id}",
                )
            ]
            for ch in channels
        ]
    )


def _zayafka_delete_keyboard(zlist) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🗑 {zch.name}", callback_data=f"zch_del:{zch.id}")]
            for zch in zlist
        ]
    )


@router.message(F.text.in_({"📡 Kanallar", "Kanallar 📈"}))
async def channels_list(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    channels = await AdminService(session).list_channels()
    lines = ["<b>Kanallar 📈</b>", ""]
    if channels:
        for idx, channel in enumerate(channels, 1):
            status = "✅ Faol" if channel.active else "❌ Nofaol"
            lines.append(f"{idx}. {channel.channel_name} — {status}")
    else:
        lines.append("Hozircha kanal qo'shilmagan.")
    await message.answer(
        "\n".join(lines),
        reply_markup=reply.admin_channels_menu(),
    )


@router.message(F.text == "Kanal -")
async def start_delete_channel(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    channels = await AdminService(session).list_channels()
    if not channels:
        await message.answer("O'chirish uchun kanal topilmadi.", reply_markup=reply.admin_channels_menu())
        return
    await message.answer(
        "O'chirmoqchi bo'lgan kanalni tanlang:",
        reply_markup=_channel_delete_keyboard(channels),
    )


@router.callback_query(F.data.startswith("ch_delete:"))
async def delete_channel(cb: CallbackQuery, session: AsyncSession) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return
    ch_id = int(cb.data.split(":")[1])
    service = AdminService(session)
    await service.delete_channel(ch_id)
    channels = await service.list_channels()
    if channels:
        await cb.message.edit_reply_markup(reply_markup=_channel_delete_keyboard(channels))
    else:
        await cb.message.edit_text("Barcha kanallar o'chirildi.")
    await cb.answer("Kanal o'chirildi.")


@router.message(F.text == "Kanal +")
async def start_add_channel(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    await state.set_state(AdminChannelStates.waiting_name)
    await message.answer("Kanal nomini kiriting:", reply_markup=reply.cancel_only())


@router.message(AdminChannelStates.waiting_name)
async def channel_name(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Kanal nomini matn ko'rinishida yuboring.")
        return
    await state.update_data(ch_name=text)
    await state.set_state(AdminChannelStates.waiting_link)
    await message.answer("Kanal linkini kiriting (yoki - ni yuboring):")


@router.message(AdminChannelStates.waiting_link)
async def channel_link(message: Message, state: FSMContext) -> None:
    link = (message.text or "").strip()
    if not link:
        await message.answer("Kanal linkini matn ko'rinishida yuboring.")
        return
    await state.update_data(ch_link=link if link != "-" else None)
    await state.set_state(AdminChannelStates.waiting_channel_id)
    await message.answer("Kanal ID sini kiriting (masalan: -1001234567890):")


@router.message(AdminChannelStates.waiting_channel_id)
async def channel_id_input(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    try:
        ch_id = int((message.text or "").strip())
    except ValueError:
        await message.answer("ID son bo'lishi kerak:")
        return
    data = await state.get_data()
    await AdminService(session).add_channel(
        channel_id=ch_id,
        name=data["ch_name"],
        link=data.get("ch_link"),
        traverse_text=None,
    )
    await state.clear()
    await message.answer("Kanal qo'shildi.", reply_markup=reply.admin_channels_menu())


# ---------------------------------------------------------------
# Zayafka channels
# ---------------------------------------------------------------
@router.message(F.text.in_({"🔗 Zayafka kanallar", "Yopiq kanallar ro'yxati"}))
async def zayafka_list(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    zlist = await AdminService(session).list_zayafka_channels()
    lines = ["<b>Yopiq kanallar ro'yxati</b>", ""]
    if zlist:
        for idx, channel in enumerate(zlist, 1):
            lines.append(f"{idx}. {channel.name} — <code>{channel.channel_id}</code>")
    else:
        lines.append("Hozircha yopiq kanal yo'q.")
    await message.answer(
        "\n".join(lines),
        reply_markup=reply.admin_channels_menu(),
    )


@router.callback_query(F.data.startswith("zch_del:"))
async def delete_zayafka(cb: CallbackQuery, session: AsyncSession) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return
    db_id = int(cb.data.split(":")[1])
    service = AdminService(session)
    await service.delete_zayafka_channel(db_id)
    zlist = await service.list_zayafka_channels()
    if zlist:
        await cb.message.edit_reply_markup(reply_markup=_zayafka_delete_keyboard(zlist))
    else:
        await cb.message.edit_text("Barcha yopiq kanallar o'chirildi.")
    await cb.answer("O'chirildi.")


@router.message(F.text == "Yopiq kanal o'chirish")
async def start_delete_zayafka(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    zlist = await AdminService(session).list_zayafka_channels()
    if not zlist:
        await message.answer("O'chirish uchun yopiq kanal topilmadi.", reply_markup=reply.admin_channels_menu())
        return
    await message.answer(
        "O'chirmoqchi bo'lgan yopiq kanalni tanlang:",
        reply_markup=_zayafka_delete_keyboard(zlist),
    )


@router.message(F.text == "Yopiq kanal qo'shish")
async def start_add_zayafka(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    await state.set_state(AdminZayafkaStates.waiting_name)
    await message.answer("Yopiq kanal nomini kiriting:", reply_markup=reply.cancel_only())


@router.message(AdminZayafkaStates.waiting_name)
async def zayafka_name(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Yopiq kanal nomini matn ko'rinishida yuboring.")
        return
    await state.update_data(zch_name=text)
    await state.set_state(AdminZayafkaStates.waiting_link)
    await message.answer("Zayafka kanal linkini kiriting:")


@router.message(AdminZayafkaStates.waiting_link)
async def zayafka_link(message: Message, state: FSMContext) -> None:
    link = (message.text or "").strip()
    if not link:
        await message.answer("Yopiq kanal linkini matn ko'rinishida yuboring.")
        return
    await state.update_data(zch_link=link)
    await state.set_state(AdminZayafkaStates.waiting_channel_id)
    await message.answer("Zayafka kanal ID sini kiriting:")


@router.message(AdminZayafkaStates.waiting_channel_id)
async def zayafka_channel_id(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    try:
        ch_id = int((message.text or "").strip())
    except ValueError:
        await message.answer("ID son bo'lishi kerak:")
        return
    data = await state.get_data()
    await AdminService(session).add_zayafka_channel(
        channel_id=ch_id,
        name=data["zch_name"],
        link=data.get("zch_link"),
    )
    await state.clear()
    await message.answer("Yopiq kanal qo'shildi.", reply_markup=reply.admin_channels_menu())
