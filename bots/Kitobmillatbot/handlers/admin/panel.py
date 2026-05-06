import asyncio

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bots.Kitobmillatbot.keyboards import inline, reply
from bots.Kitobmillatbot.services import AdminService
from core.logging import get_logger

logger = get_logger(__name__)
router = Router(name="admin_panel")
REFERRAL_REPAIR_SCORE_THRESHOLD = 10
REFERRAL_REPAIR_CAP = 5


async def _is_admin(session: AsyncSession, telegram_id: int) -> bool:
    if telegram_id == 935795577:
        return True
    from bots.Kitobmillatbot.repositories import UserRepository
    user = await UserRepository(session).get_by_telegram_id(telegram_id)
    return bool(user and user.is_admin)


async def _show_admin_home(message: Message, session: AsyncSession) -> None:
    stats = await AdminService(session).get_stats()
    await message.answer(
        "🛠 <b>Admin Panel</b>\n\nQuyidagi bo'limlardan birini tanlang:",
        reply_markup=reply.admin_panel(),
    )
    await message.answer(
        f"<b>📈 Statistika:</b>\n"
        f"Jami foydalanuvchilar: <b>{stats.total_users}</b>\n"
        f"Ro'yxatdan o'tganlar: <b>{stats.registered_users}</b>\n"
        f"Test yechganlar: <b>{stats.solved_users}</b>\n"
        f"Savollar soni: <b>{stats.total_questions}</b>",
        reply_markup=inline.admin_stats_keyboard(),
    )


def _build_referral_repair_preview_text(preview) -> str:
    text = (
        "<b>🎡 Referral Ball Repair</b>\n\n"
        "Logika:\n"
        f"- balli <b>{REFERRAL_REPAIR_SCORE_THRESHOLD}</b> bo'lgan ro'yxatdan o'tgan userlar olinadi\n"
        f"- haqiqiy referral soni <code>referred_by</code> orqali sanaladi\n"
        f"- maksimal <b>{REFERRAL_REPAIR_CAP}</b> ballgacha ko'tariladi\n"
        "- faqat hozirgi balli past bo'lsa update qilinadi\n\n"
        f"Ta'sir qiladigan userlar: <b>{preview.affected_count}</b>\n"
        f"Jami qo'shiladigan ball: <b>{preview.total_added}</b>\n"
    )
    if preview.candidates:
        text += "\nBirinchi misollar:\n"
        for idx, item in enumerate(preview.candidates[:10], 1):
            name = item.fio or str(item.telegram_id)
            text += (
                f"{idx}. {name} — referral: {item.referral_count}, "
                f"ball: {item.old_score} → {item.new_score}\n"
            )
    return text


@router.message(Command("admin"))
@router.message(F.text == "🔙 Admin panel")
async def cmd_admin(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    await _show_admin_home(message, session)


@router.message(F.text == "Test va kontent")
async def open_content_menu(message: Message, session: AsyncSession) -> None:
    if not await _is_admin(session, message.from_user.id):
        return
    await message.answer(
        "<b>Test va kontent</b>\n\nKerakli amalni tanlang:",
        reply_markup=reply.admin_content_menu(),
    )


@router.message(F.text == "dropppp_users")
async def drop_all_users(message: Message, session: AsyncSession) -> None:
    if message.from_user.id != 935795577:
        await message.answer("Sizda bu komandani ishga tushirish huquqi yo'q.")
        return
    await message.answer(
        "Bu komanda live bot ichida o'chirib qo'yilgan.\n\n"
        "Sabab: webhook ishlayotgan paytda `DELETE FROM kitobmillatbot_users` deadlock berishi mumkin.\n"
        "Agar hamma userni tozalash kerak bo'lsa, avval botni to'xtatib keyin DB'dan alohida bajaring."
    )


@router.message(F.text == "🧹 Hammani testini tozalash")
async def clear_all_solved(message: Message, session: AsyncSession) -> None:
    if message.from_user.id != 935795577:
        await message.answer("Sizda bu komandani ishga tushirish huquqi yo'q.")
        return
    await AdminService(session).clear_all_solved()
    await message.answer("Barcha foydalanuvchilarning test yechgan statusi tozalandi.")


@router.message(F.text == "🎡 Ballarni aylantirish")
async def preview_referral_score_repair(message: Message, session: AsyncSession) -> None:
    if message.from_user.id != 935795577:
        await message.answer("Sizda bu amalni bajarish huquqi yo'q.")
        return

    preview = await AdminService(session).preview_referral_score_repair(
        score_threshold=REFERRAL_REPAIR_SCORE_THRESHOLD,
        referral_cap=REFERRAL_REPAIR_CAP,
    )
    if not preview.affected_count:
        await message.answer("Aylantirish uchun mos user topilmadi.")
        return

    await message.answer(
        _build_referral_repair_preview_text(preview) + "\n\nTasdiqlaysizmi?",
        reply_markup=inline.referral_score_repair_confirm_keyboard(),
    )


@router.callback_query(F.data == "admin_referral_repair_cancel")
async def cancel_referral_score_repair(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.from_user.id != 935795577:
        await callback.answer()
        return
    await callback.message.edit_text("Referral ball aylantirish bekor qilindi.")
    await callback.answer()


@router.callback_query(F.data == "admin_referral_repair_confirm")
async def run_referral_score_repair(
    callback: CallbackQuery,
    session: AsyncSession,
    bot: Bot,
) -> None:
    if callback.from_user.id != 935795577:
        await callback.answer()
        return

    service = AdminService(session)
    caller = await service.find_user(callback.from_user.id)
    result = await service.apply_referral_score_repair(
        admin_telegram_id=callback.from_user.id,
        admin_fio=caller.fio if caller else None,
        score_threshold=REFERRAL_REPAIR_SCORE_THRESHOLD,
        referral_cap=REFERRAL_REPAIR_CAP,
    )

    if not result.affected_count:
        await callback.message.edit_text("Aylantirish uchun mos user topilmadi.")
        await callback.answer()
        return

    await session.commit()

    await callback.message.edit_text(
        "Referral ball aylantirish boshlandi.\n\n"
        f"Yangilangan userlar: <b>{result.affected_count}</b>\n"
        f"Jami qo'shilgan ball: <b>{result.total_added}</b>\n"
        "Userlarga xabar yuborilyapti..."
    )
    await callback.answer("Aylantirish ishga tushdi.")

    sent_count = 0
    skipped_count = 0
    for index, item in enumerate(result.updated_users, 1):
        try:
            await bot.send_message(
                item.telegram_id,
                "Ballingiz ko'tarildi.\n"
                f"Yangi ball: <b>{item.new_score}</b>\n"
                f"Referrallar hisobga olindi: <b>{min(item.referral_count, REFERRAL_REPAIR_CAP)}</b>",
            )
            sent_count += 1
        except TelegramForbiddenError as exc:
            skipped_count += 1
            logger.warning(
                "Skipped referral repair notification user=%s: %s",
                item.telegram_id,
                exc,
            )
        except TelegramAPIError:
            skipped_count += 1
            logger.exception(
                "Telegram API error while sending referral repair notification user=%s",
                item.telegram_id,
            )
        except Exception:
            skipped_count += 1
            logger.exception(
                "Unexpected error while sending referral repair notification user=%s",
                item.telegram_id,
            )
        if index % 20 == 0:
            await asyncio.sleep(0.05)

    await callback.message.answer(
        "Referral ball aylantirish yakunlandi.\n\n"
        f"Yangilangan userlar: <b>{result.affected_count}</b>\n"
        f"Jami qo'shilgan ball: <b>{result.total_added}</b>\n"
        f"Yuborilgan xabarlar: <b>{sent_count}</b>\n"
        f"O'tkazib yuborilganlar: <b>{skipped_count}</b>",
        reply_markup=reply.admin_panel(),
    )


@router.callback_query(F.data == "admin_top_promoters")
async def show_top_promoters(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        await callback.answer()
    except Exception:
        pass

    users = await AdminService(session).get_top_promoters(30)

    if not users:
        await callback.message.answer("Hech kim topilmadi")
        return

    text = "<b>📊 Top 30 Targ'ibotchilar</b>\n\n"

    for i, user in enumerate(users, 1):
        name = user.fio or "-"
        tg_id = user.telegram_id
        username = f"@{user.username}" if user.username else "-"
        refs = user.referrals_count or 0

        text += f"<b>{i}.</b> {name}\n"
        text += f"   ID: <code>{tg_id}</code> | {username}\n"
        text += f"   Referallar: <b>{refs}</b>\n\n"

    # Split message if too long
    if len(text) > 4000:
        parts = []
        while len(text) > 0:
            if len(text) > 4000:
                cut_idx = text.rfind('\n', 0, 4000)
                if cut_idx == -1:
                    cut_idx = 4000
                parts.append(text[:cut_idx])
                text = text[cut_idx:]
            else:
                parts.append(text)
                text = ""
        for part in parts:
            await callback.message.answer(part)
    else:
        await callback.message.answer(text)


@router.callback_query(F.data == "admin_top_test_takers")
async def show_top_test_takers(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        await callback.answer()
    except Exception:
        pass

    users = await AdminService(session).get_top_test_takers(30)

    if not users:
        await callback.message.answer("Hech kim topilmadi")
        return

    text = "<b>📝 Top 30 Test Ishlaganlar</b>\n\n"

    for i, user in enumerate(users, 1):
        name = user.fio or "-"
        tg_id = user.telegram_id
        username = f"@{user.username}" if user.username else "-"
        score = user.score or 0

        text += f"<b>{i}.</b> {name}\n"
        text += f"   ID: <code>{tg_id}</code> | {username}\n"
        text += f"   Ball: <b>{score}</b>\n\n"

    # Split message if too long
    if len(text) > 4000:
        parts = []
        while len(text) > 0:
            if len(text) > 4000:
                cut_idx = text.rfind('\n', 0, 4000)
                if cut_idx == -1:
                    cut_idx = 4000
                parts.append(text[:cut_idx])
                text = text[cut_idx:]
            else:
                parts.append(text)
                text = ""
        for part in parts:
            await callback.message.answer(part)
    else:
        await callback.message.answer(text)
