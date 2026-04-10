from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bots.kitobxon.models import Channel, Question, ZayafkaChannel
from bots.kitobxon.services.quiz_service import QuestionPayload


def subscription_keyboard(
    missing_channels: list[Channel],
    missing_zayafka: list[ZayafkaChannel],
) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    for ch in missing_channels:
        buttons.append(
            [InlineKeyboardButton(text=f"➡️ {ch.channel_name}", url=ch.channel_link or "")]
        )
    for zch in missing_zayafka:
        buttons.append(
            [InlineKeyboardButton(text=f"➡️ {zch.name}", url=zch.link or "")]
        )
    buttons.append(
        [InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_subscription")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def quiz_keyboard(payload: QuestionPayload) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=opt, callback_data=f"ans:{opt}")]
        for opt in payload.options
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def channels_list_keyboard(
    channels, *, prefix: str = "ch_toggle"
) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{'✅' if ch.active else '❌'} {ch.channel_name}",
                callback_data=f"{prefix}:{ch.id}",
            )
        ]
        for ch in channels
    ]
    buttons.append(
        [InlineKeyboardButton(text="➕ Yangi qo'shish", callback_data="ch_add")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def zayafka_list_keyboard(zlist) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=f"🗑 {zch.name}",
                callback_data=f"zch_del:{zch.id}",
            )
        ]
        for zch in zlist
    ]
    buttons.append(
        [InlineKeyboardButton(text="➕ Yangi qo'shish", callback_data="zch_add")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def quiz_type_keyboard(current_type: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{'✅ ' if current_type == 'web' else ''}💬 Web (tugmalar)",
                    callback_data="qt:web",
                ),
                InlineKeyboardButton(
                    text=f"{'✅ ' if current_type == 'quiz' else ''}📊 Quiz (poll)",
                    callback_data="qt:quiz",
                ),
            ]
        ]
    )


def questions_list_keyboard(questions) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=f"🗑 {q.text[:40]}",
                callback_data=f"q_del:{q.id}",
            )
        ]
        for q in questions[:30]
    ]
    buttons.append(
        [InlineKeyboardButton(text="➕ Savol qo'shish", callback_data="q_add")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def user_action_keyboard(telegram_id: int, is_admin: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💯 Ball o'zgartirish",
                    callback_data=f"u_score:{telegram_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Testni reset",
                    callback_data=f"u_reset:{telegram_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{'🚫 Admin olib tashlash' if is_admin else '⭐ Admin qilish'}",
                    callback_data=f"u_admin:{telegram_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑 O'chirish",
                    callback_data=f"u_delete:{telegram_id}",
                )
            ],
        ]
    )


def admin_stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Targ'ibotchilar",
                    callback_data="admin_top_promoters",
                ),
                InlineKeyboardButton(
                    text="📝 Test ishlaganlar",
                    callback_data="admin_top_test_takers",
                ),
            ]
        ]
    )
