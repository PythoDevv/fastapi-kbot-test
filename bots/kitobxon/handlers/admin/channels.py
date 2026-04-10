from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.keyboards import inline, reply
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
@router.message(F.text == "📡 Kanallar")
async def channels_list(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    channels = await AdminService(session).list_channels()
    await message.answer(
        "Kanallar:",
        reply_markup=inline.channels_list_keyboard(channels, prefix="ch_toggle"),
    )


@router.callback_query(F.data.startswith("ch_toggle:"))
async def toggle_channel(cb: CallbackQuery, session: AsyncSession) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return
    ch_id = int(cb.data.split(":")[1])
    service = AdminService(session)
    channels = await service.list_channels()
    ch = next((c for c in channels if c.id == ch_id), None)
    if ch:
        await service.toggle_channel(ch_id, not ch.active)
    channels = await service.list_channels()
    await cb.message.edit_reply_markup(
        reply_markup=inline.channels_list_keyboard(channels, prefix="ch_toggle")
    )
    await cb.answer()


@router.callback_query(F.data == "ch_add")
async def start_add_channel(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return
    await state.set_state(AdminChannelStates.waiting_name)
    await cb.message.answer("Kanal nomini kiriting:", reply_markup=reply.cancel_only())
    await cb.answer()


@router.message(AdminChannelStates.waiting_name)
async def channel_name(message: Message, state: FSMContext) -> None:
    await state.update_data(ch_name=message.text.strip())
    await state.set_state(AdminChannelStates.waiting_link)
    await message.answer("Kanal linkini kiriting (yoki - ni yuboring):")


@router.message(AdminChannelStates.waiting_link)
async def channel_link(message: Message, state: FSMContext) -> None:
    link = message.text.strip()
    await state.update_data(ch_link=link if link != "-" else None)
    await state.set_state(AdminChannelStates.waiting_channel_id)
    await message.answer("Kanal ID sini kiriting (masalan: -1001234567890):")


@router.message(AdminChannelStates.waiting_channel_id)
async def channel_id_input(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    try:
        ch_id = int(message.text.strip())
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
    await message.answer("Kanal qo'shildi.", reply_markup=reply.admin_panel())


# ---------------------------------------------------------------
# Zayafka channels
# ---------------------------------------------------------------
@router.message(F.text == "🔗 Zayafka kanallar")
async def zayafka_list(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    zlist = await AdminService(session).list_zayafka_channels()
    await message.answer(
        "Zayafka kanallar:",
        reply_markup=inline.zayafka_list_keyboard(zlist),
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
    await cb.message.edit_reply_markup(
        reply_markup=inline.zayafka_list_keyboard(zlist)
    )
    await cb.answer("O'chirildi.")


@router.callback_query(F.data == "zch_add")
async def start_add_zayafka(
    cb: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    if not await _is_admin(session, cb.from_user.id):
        await cb.answer()
        return
    await state.set_state(AdminZayafkaStates.waiting_name)
    await cb.message.answer("Zayafka kanal nomini kiriting:", reply_markup=reply.cancel_only())
    await cb.answer()


@router.message(AdminZayafkaStates.waiting_name)
async def zayafka_name(message: Message, state: FSMContext) -> None:
    await state.update_data(zch_name=message.text.strip())
    await state.set_state(AdminZayafkaStates.waiting_link)
    await message.answer("Zayafka kanal linkini kiriting:")


@router.message(AdminZayafkaStates.waiting_link)
async def zayafka_link(message: Message, state: FSMContext) -> None:
    await state.update_data(zch_link=message.text.strip())
    await state.set_state(AdminZayafkaStates.waiting_channel_id)
    await message.answer("Zayafka kanal ID sini kiriting:")


@router.message(AdminZayafkaStates.waiting_channel_id)
async def zayafka_channel_id(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    try:
        ch_id = int(message.text.strip())
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
    await message.answer("Zayafka kanal qo'shildi.", reply_markup=reply.admin_panel())
