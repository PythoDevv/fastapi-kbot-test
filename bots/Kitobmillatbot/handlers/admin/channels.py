import json

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.Kitobmillatbot.keyboards import reply
from bots.Kitobmillatbot.repositories import ContentRepository
from bots.Kitobmillatbot.services import AdminService
from bots.Kitobmillatbot.states import AdminChannelStates, AdminZayafkaStates

router = Router(name="admin_channels")


def _message_text(message: Message) -> str:
    return (message.text or message.caption or "").strip()


def _draft_key(kind: str, telegram_id: int) -> str:
    return f"draft:{kind}:{telegram_id}"


def _normalize_channel_link(link: str, *, allow_skip: bool) -> str | None:
    value = link.strip()
    if allow_skip and value == "-":
        return None
    if value.startswith("https://t.me/") or value.startswith("http://t.me/"):
        return value
    if value.startswith("t.me/"):
        return f"https://{value}"
    return None


async def _save_draft(
    session: AsyncSession,
    *,
    kind: str,
    telegram_id: int,
    payload: dict,
) -> None:
    await ContentRepository(session).upsert(
        _draft_key(kind, telegram_id),
        text=json.dumps(payload, ensure_ascii=False),
    )


async def _load_draft(
    session: AsyncSession,
    *,
    kind: str,
    telegram_id: int,
) -> dict | None:
    obj = await ContentRepository(session).get_by_key(_draft_key(kind, telegram_id))
    if obj is None or not obj.text:
        return None
    try:
        return json.loads(obj.text)
    except json.JSONDecodeError:
        return None


async def _clear_draft(session: AsyncSession, *, kind: str, telegram_id: int) -> None:
    await ContentRepository(session).delete_by_key(_draft_key(kind, telegram_id))


async def _set_kind_state(state: FSMContext, *, kind: str, step: str) -> None:
    if kind == "channel":
        mapping = {
            "name": AdminChannelStates.waiting_name,
            "link": AdminChannelStates.waiting_link,
            "channel_id": AdminChannelStates.waiting_channel_id,
        }
    else:
        mapping = {
            "name": AdminZayafkaStates.waiting_name,
            "link": AdminZayafkaStates.waiting_link,
            "channel_id": AdminZayafkaStates.waiting_channel_id,
        }
    await state.set_state(mapping[step])


async def _process_channel_draft(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    *,
    kind: str,
) -> bool:
    draft = await _load_draft(session, kind=kind, telegram_id=message.from_user.id)
    if not draft:
        return False

    text = _message_text(message)
    if not text:
        await message.answer("Matn ko'rinishida yuboring.")
        return True

    if text == "Bekor qilish":
        await _clear_draft(session, kind=kind, telegram_id=message.from_user.id)
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=reply.admin_channels_menu())
        return True

    step = draft.get("step")
    if step == "name":
        draft["name"] = text
        draft["step"] = "link"
        await _save_draft(session, kind=kind, telegram_id=message.from_user.id, payload=draft)
        await _set_kind_state(state, kind=kind, step="link")
        await message.answer(
            "Kanal linkini kiriting (yoki - ni yuboring):"
            if kind == "channel"
            else "Zayafka kanal linkini kiriting:"
        )
        return True

    if step == "link":
        normalized_link = _normalize_channel_link(text, allow_skip=kind == "channel")
        if normalized_link is None and not (kind == "channel" and text == "-"):
            await message.answer(
                "To'g'ri link yuboring. Masalan: https://t.me/kanal yoki t.me/kanal"
            )
            return True
        draft["link"] = normalized_link
        draft["step"] = "channel_id"
        await _save_draft(session, kind=kind, telegram_id=message.from_user.id, payload=draft)
        await _set_kind_state(state, kind=kind, step="channel_id")
        await message.answer(
            "Kanal ID sini kiriting (masalan: -1001234567890):"
            if kind == "channel"
            else "Zayafka kanal ID sini kiriting (masalan: -1001234567890):"
        )
        return True

    if step == "channel_id":
        try:
            channel_id = int(text)
        except ValueError:
            await message.answer("ID son bo'lishi kerak. Masalan: -1001234567890")
            return True

        service = AdminService(session)
        if kind == "channel":
            await service.add_channel(
                channel_id=channel_id,
                name=draft["name"],
                link=draft.get("link"),
                traverse_text=None,
            )
            success_text = "Kanal qo'shildi."
        else:
            await service.add_zayafka_channel(
                channel_id=channel_id,
                name=draft["name"],
                link=draft.get("link"),
            )
            success_text = "Yopiq kanal qo'shildi."

        await _clear_draft(session, kind=kind, telegram_id=message.from_user.id)
        await state.clear()
        await message.answer(success_text, reply_markup=reply.admin_channels_menu())
        return True

    return False


async def _is_admin(session: AsyncSession, telegram_id: int) -> bool:
    if telegram_id == 935795577:
        return True
    from bots.Kitobmillatbot.repositories import UserRepository
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
    await _save_draft(
        session,
        kind="channel",
        telegram_id=message.from_user.id,
        payload={"step": "name"},
    )
    await state.set_state(AdminChannelStates.waiting_name)
    await message.answer("Kanal nomini kiriting:", reply_markup=reply.cancel_only())


@router.message(
    F.text == "Bekor qilish",
    AdminChannelStates.waiting_name,
)
@router.message(
    F.text == "Bekor qilish",
    AdminChannelStates.waiting_link,
)
@router.message(
    F.text == "Bekor qilish",
    AdminChannelStates.waiting_channel_id,
)
async def cancel_channel_add(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await _clear_draft(session, kind="channel", telegram_id=message.from_user.id)
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=reply.admin_channels_menu())


@router.message(AdminChannelStates.waiting_name)
async def channel_name(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await _process_channel_draft(message, state, session, kind="channel")


@router.message(AdminChannelStates.waiting_link)
async def channel_link(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await _process_channel_draft(message, state, session, kind="channel")


@router.message(AdminChannelStates.waiting_channel_id)
async def channel_id_input(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await _process_channel_draft(message, state, session, kind="channel")


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
    await _save_draft(
        session,
        kind="zch",
        telegram_id=message.from_user.id,
        payload={"step": "name"},
    )
    await state.set_state(AdminZayafkaStates.waiting_name)
    await message.answer("Yopiq kanal nomini kiriting:", reply_markup=reply.cancel_only())


@router.message(
    F.text == "Bekor qilish",
    AdminZayafkaStates.waiting_name,
)
@router.message(
    F.text == "Bekor qilish",
    AdminZayafkaStates.waiting_link,
)
@router.message(
    F.text == "Bekor qilish",
    AdminZayafkaStates.waiting_channel_id,
)
async def cancel_zayafka_add(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await _clear_draft(session, kind="zch", telegram_id=message.from_user.id)
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=reply.admin_channels_menu())


@router.message(AdminZayafkaStates.waiting_name)
async def zayafka_name(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await _process_channel_draft(message, state, session, kind="zch")


@router.message(AdminZayafkaStates.waiting_link)
async def zayafka_link(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await _process_channel_draft(message, state, session, kind="zch")


@router.message(AdminZayafkaStates.waiting_channel_id)
async def zayafka_channel_id(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await _process_channel_draft(message, state, session, kind="zch")
