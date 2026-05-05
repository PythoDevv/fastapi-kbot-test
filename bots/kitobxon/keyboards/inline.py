from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

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


def webapp_quiz_keyboard(webapp_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧑‍💻 Testni boshlash", web_app=WebAppInfo(url=webapp_url))]
        ]
    )


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
            ],
            [
                InlineKeyboardButton(
                    text=f"{'✅ ' if current_type == 'webapp' else ''}🧑‍💻 WebApp (widget)",
                    callback_data="qt:webapp",
                ),
            ],
        ]
    )


def quiz_status_keyboard(is_active: bool, is_waiting: bool, is_finished: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⏸ To'xtatish" if (is_active and not is_waiting) else "▶️ Boshlash",
                    callback_data="qs_toggle",
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
        [
            InlineKeyboardButton(text="➕ Qo'shish", callback_data="q_add"),
            InlineKeyboardButton(text="📄 Namuna", callback_data="q_template"),
        ]
    )
    buttons.append(
        [
            InlineKeyboardButton(text="📥 Import", callback_data="q_import_start"),
            InlineKeyboardButton(text="📤 Export", callback_data="q_export"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def user_action_keyboard(telegram_id: int, is_admin: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💯 Ball o'zgartirish",
                    callback_data=f"u_score:{telegram_id}",
                ),
                InlineKeyboardButton(
                    text="👥 Referallar",
                    callback_data=f"u_referrals:{telegram_id}",
                ),
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


def content_list_keyboard(contents: list | None = None) -> InlineKeyboardMarkup:
    """Keyboard with content items to manage — dynamic from DB + add button"""
    from bots.kitobxon.models import ContentText
    buttons = []
    if contents:
        for ct in contents:
            buttons.append(
                [InlineKeyboardButton(text=f"📝 {ct.key}", callback_data=f"ct_manage:{ct.key}")]
            )
    buttons.append(
        [InlineKeyboardButton(text="➕ Yangi qo'shish", callback_data="ct_add")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def content_manage_keyboard(key: str, require_link: bool = False) -> InlineKeyboardMarkup:
    """Management keyboard for a specific content item"""
    link_text = f"🔗 Link {'✅' if require_link else '❌'}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"ct_edit:{key}"),
                InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"ct_delete:{key}"),
            ],
            [InlineKeyboardButton(text=link_text, callback_data=f"ct_link:{key}")],
        ]
    )


def results_main_keyboard() -> InlineKeyboardMarkup:
    """Main results keyboard with Test and Referral buttons"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Testim", callback_data="res_test"),
                InlineKeyboardButton(text="👥 Referallarim", callback_data="res_referral"),
            ]
        ]
    )


def results_back_keyboard() -> InlineKeyboardMarkup:
    """Back to main results menu"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="res_back")]
        ]
    )


def quiz_settings_full_keyboard(
    is_active: bool,
    is_waiting: bool,
    is_finished: bool,
    require_phone: bool,
    current_type: str,
) -> InlineKeyboardMarkup:
    """Full settings keyboard with status, phone toggle, and quiz type selection"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⏸ To'xtatish" if (is_active and not is_waiting) else "▶️ Boshlash",
                    callback_data="qs_toggle",
                ),
                InlineKeyboardButton(
                    text=f"📱 Telefon {'✅' if require_phone else '❌'}",
                    callback_data="ps:phone",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"{'✅ ' if current_type == 'web' else ''}💬 Web",
                    callback_data="qt:web",
                ),
                InlineKeyboardButton(
                    text=f"{'✅ ' if current_type == 'quiz' else ''}📊 Quiz",
                    callback_data="qt:quiz",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"{'✅ ' if current_type == 'webapp' else ''}🧑‍💻 WebApp",
                    callback_data="qt:webapp",
                ),
            ],
        ]
    )


def cancel_keyboard() -> InlineKeyboardMarkup:
    """Simple cancel button for inline keyboards (used with edit_text)"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Bekor qilish", callback_data="cancel")]
        ]
    )
