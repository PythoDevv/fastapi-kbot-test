import asyncio
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, PollAnswer
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.config import QuizType
from bots.kitobxon.exceptions import (
    AlreadySolvedError,
    KitobxonError,
    QuizAlreadyStartedError,
    QuizFinishedError,
    QuizNotActiveError,
    QuizWaitingError,
    SubscriptionRequiredError,
)
from bots.kitobxon.keyboards import inline, reply
from bots.kitobxon.services import QuizService, SubsService
from bots.kitobxon.services.quiz_service import QuestionPayload
from bots.kitobxon.states import QuizStates
from core.logging import get_logger

logger = get_logger(__name__)
router = Router(name="quiz")
MIN_CONFIRMED_REFERRALS_TO_START = 5

# Timeout task registry for WEB mode questions
_timeout_tasks: dict[int, asyncio.Task] = {}


def _format_question(payload: QuestionPayload) -> str:
    return (
        f"<b>Savol {payload.index + 1}/{payload.total}</b>\n\n"
        f"{payload.question.text}"
    )


def _finish_text(score: int, total_questions: int) -> str:
    return (
        "Testni yechib bo'ldingiz!\n\n"
        f"To'g'ri javoblar soni: <b>{score}/{total_questions}</b>"
    )


async def _send_finish_and_menu(
    message: Message,
    *,
    score: int,
    total_questions: int,
) -> None:
    await message.answer(_finish_text(score, total_questions))
    await message.answer("Asosiy menyu:", reply_markup=reply.main_menu())


def _cancel_timeout(user_id: int) -> None:
    """Cancel pending timeout task for user"""
    task = _timeout_tasks.pop(user_id, None)
    if task and not task.done():
        task.cancel()


async def _timeout_task(
    bot: Bot,
    chat_id: int,
    service: QuizService,
    state: FSMContext,
    session_id: int,
    question_index: int,
    time_limit: int,
    message_id: int | None,
) -> None:
    """Auto-submit answer as timeout after time_limit seconds (WEB mode)"""
    try:
        await asyncio.sleep(time_limit)

        try:
            result = await service.submit_answer(
                session_id=session_id,
                question_index=question_index,
                selected_text="",
                time_taken=time_limit,
                is_timeout=True,
            )
        except (QuizNotActiveError, QuizFinishedError):
            await bot.send_message(
                chat_id, "Test yakunlandi.", reply_markup=reply.main_menu()
            )
            return

        if message_id:
            try:
                await bot.delete_message(chat_id, message_id)
            except Exception:
                pass

        if result.is_last:
            await bot.send_message(chat_id, _finish_text(result.score, result.total_questions))
            await bot.send_message(chat_id, "Asosiy menyu:", reply_markup=reply.main_menu())
            await state.clear()
            return

        # Send next question
        await state.update_data(index=result.next_question.index)
        await state.update_data(
            question_sent_at=datetime.utcnow().isoformat()
        )

        next_message = await bot.send_message(
            chat_id,
            _format_question(result.next_question),
            reply_markup=inline.quiz_keyboard(result.next_question),
            protect_content=True,
        )
        await state.update_data(question_message_id=next_message.message_id)

        # Schedule next timeout
        _schedule_timeout(
            chat_id,
            bot,
            service,
            state,
            session_id,
            result.next_question.index,
            time_limit,
            next_message.message_id,
        )

    except asyncio.CancelledError:
        pass


async def _timeout_task_poll(
    bot: Bot,
    chat_id: int,
    service: QuizService,
    poll_id: str,
    session_id: int,
    message_id: int,
    time_limit: int,
) -> None:
    """Auto-submit answer as timeout for QUIZ mode (native poll)"""
    try:
        await asyncio.sleep(time_limit)

        # Get poll mapping
        mapping = await service.resolve_poll(poll_id)
        if not mapping:
            return

        try:
            result = await service.submit_answer(
                session_id=mapping.session_id,
                question_index=mapping.question_index,
                selected_text="",
                time_taken=time_limit,
                is_timeout=True,
            )
        except (QuizNotActiveError, QuizFinishedError):
            await service.delete_poll(poll_id)
            await bot.send_message(
                chat_id, "Test yakunlandi.", reply_markup=reply.main_menu()
            )
            return

        await service.delete_poll(poll_id)

        # Delete old poll message
        try:
            await bot.delete_message(chat_id, message_id)
        except Exception:
            pass

        if result.is_last:
            await bot.send_message(chat_id, _finish_text(result.score, result.total_questions))
            await bot.send_message(chat_id, "Asosiy menyu:", reply_markup=reply.main_menu())
            return

        # Send next poll
        settings = await service.quiz.get_settings()
        time_limit_next = settings.time_limit_seconds if settings else 40

        if result.next_question is None:
            logger.error(f"Next question is None after timeout for session {mapping.session_id}")
            return

        await _send_poll_question(
            bot=bot,
            chat_id=chat_id,
            service=service,
            state=None,
            session_id=mapping.session_id,
            payload=result.next_question,
            time_limit=time_limit_next,
        )

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.exception(f"Error in _timeout_task_poll: {e}")


def _schedule_timeout(
    user_id: int,
    bot: Bot,
    service: QuizService,
    state: FSMContext,
    session_id: int,
    question_index: int,
    time_limit: int,
    message_id: int | None,
) -> None:
    """Schedule a timeout task for user (WEB mode)"""
    _cancel_timeout(user_id)
    task = asyncio.create_task(
        _timeout_task(
            bot,
            user_id,
            service,
            state,
            session_id,
            question_index,
            time_limit,
            message_id,
        )
    )
    _timeout_tasks[user_id] = task


def _schedule_timeout_poll(
    user_id: int,
    bot: Bot,
    service: QuizService,
    poll_id: str,
    session_id: int,
    message_id: int,
    time_limit: int,
) -> None:
    """Schedule a timeout task for poll (QUIZ mode)"""
    _cancel_timeout(user_id)
    task = asyncio.create_task(
        _timeout_task_poll(bot, user_id, service, poll_id, session_id, message_id, time_limit)
    )
    _timeout_tasks[user_id] = task


@router.message(F.text == "Test savollarini ishlash 🧑‍💻")
async def start_quiz(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    from bots.kitobxon.repositories import UserRepository
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(message.from_user.id)
    if not user or not user.is_registered:
        await message.answer("Avval ro'yxatdan o'ting.")
        return

    confirmed_referrals = await user_repo.count_confirmed_referrals(message.from_user.id)
    if not user.is_admin and confirmed_referrals < MIN_CONFIRMED_REFERRALS_TO_START:
        remaining = MIN_CONFIRMED_REFERRALS_TO_START - confirmed_referrals
        await message.answer(
            "Testni ishlash uchun kamida "
            f"<b>{MIN_CONFIRMED_REFERRALS_TO_START} ta</b> referral orqali odam taklif qilishingiz kerak.\n\n"
            f"Hozir tasdiqlangan referral: <b>{confirmed_referrals}</b>\n"
            f"Yana kerak: <b>{remaining}</b>",
        )
        return

    # Adminlar uchun obuna tekshiruvi yo'q
    if not user.is_admin:
        subs = SubsService(session)
        status = await subs.check_user(bot, message.from_user.id, user.id)
        if not status.all_subscribed:
            await message.answer(
                "Testni boshlash uchun avval kanallarga obuna bo'ling:",
                reply_markup=inline.subscription_keyboard(
                    status.missing_channels, status.missing_zayafka
                ),
            )
            return

    service = QuizService(session)
    result = None
    try:
        result = await service.start_session(message.from_user.id)
    except QuizWaitingError:
        settings = await service.quiz.get_settings()
        text = settings.waiting_text or "Test hali boshlanmagan. Kuting."
        if settings and settings.image_id:
            await message.answer_photo(photo=settings.image_id, caption=text)
        else:
            await message.answer(text)
        return
    except QuizFinishedError:
        settings = await service.quiz.get_settings()
        text = settings.finished_text if settings else "Test yakunlandi."
        await message.answer(text or "Test yakunlandi.")
        return
    except AlreadySolvedError:
        await message.answer("Siz testni allaqachon yakunladingiz.")
        return
    except QuizAlreadyStartedError:
        # Resume existing session
        active_session = await service.quiz.get_active_session(user.id)
        if not active_session:
            await message.answer("Sizda faol test mavjud.")
            return

        settings = await service.quiz.get_settings()
        session_quiz_type = await service.get_session_quiz_type(active_session.id)
        payload = await service.get_current_payload(active_session.id)
        if not payload or not settings or session_quiz_type is None:
            await message.answer("Sessiya topilmadi.")
            return

        await state.set_state(QuizStates.answering)
        await state.update_data(
            session_id=active_session.id,
            index=active_session.current_index,
            quiz_type=session_quiz_type.value,
            question_sent_at=datetime.utcnow().isoformat(),
        )

        if session_quiz_type == QuizType.WEBAPP:
            from core.config import settings as app_settings
            webapp_url = f"{app_settings.BASE_WEBHOOK_URL.rstrip('/')}/webapp/"
            await message.answer(
                "Testni davom ettirish uchun quyidagi tugmani bosing:",
                reply_markup=inline.webapp_quiz_keyboard(webapp_url),
            )
        elif session_quiz_type == QuizType.WEB:
            sent_message = await message.answer(
                _format_question(payload),
                reply_markup=inline.quiz_keyboard(payload),
                protect_content=True,
            )
            await state.update_data(question_message_id=sent_message.message_id)
            _schedule_timeout(
                message.chat.id,
                bot,
                service,
                state,
                active_session.id,
                active_session.current_index,
                settings.time_limit_seconds,
                sent_message.message_id,
            )
        else:
            await service.delete_session_polls(active_session.id)
            await _send_poll_question(
                bot=bot,
                chat_id=message.chat.id,
                service=service,
                state=state,
                session_id=active_session.id,
                payload=payload,
                time_limit=settings.time_limit_seconds,
            )
        return
    except KitobxonError as e:
        await message.answer(str(e))
        return

    # New session started
    await state.set_state(QuizStates.answering)
    await state.update_data(
        session_id=result.session.id,
        index=0,
        quiz_type=result.quiz_type.value,
        question_sent_at=datetime.utcnow().isoformat(),
    )

    if result.quiz_type == QuizType.WEBAPP:
        from core.config import settings as app_settings
        webapp_url = f"{app_settings.BASE_WEBHOOK_URL.rstrip('/')}/webapp/"
        await message.answer(
            "Testni boshlash uchun quyidagi tugmani bosing:",
            reply_markup=inline.webapp_quiz_keyboard(webapp_url),
        )
    elif result.quiz_type == QuizType.WEB:
        sent_message = await message.answer(
            _format_question(result.first_question),
            reply_markup=inline.quiz_keyboard(result.first_question),
            protect_content=True,
        )
        await state.update_data(question_message_id=sent_message.message_id)
        _schedule_timeout(
            message.chat.id,
            bot,
            service,
            state,
            result.session.id,
            0,
            result.settings.time_limit_seconds,
            sent_message.message_id,
        )
    else:
        await _send_poll_question(
            bot=bot,
            chat_id=message.chat.id,
            service=service,
            state=state,
            session_id=result.session.id,
            payload=result.first_question,
            time_limit=result.settings.time_limit_seconds,
        )


# ---------------------------------------------------------------
# WEB mode: inline keyboard answer
# ---------------------------------------------------------------
@router.callback_query(QuizStates.answering, F.data.startswith("ans:"))
async def handle_web_answer(
    cb: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    data = await state.get_data()
    session_id: int = data["session_id"]
    index: int = data["index"]
    current_message_id: int | None = data.get("question_message_id")

    # Cancel timeout task
    _cancel_timeout(cb.from_user.id)

    # Calculate time taken
    sent_at_str = data.get("question_sent_at")
    time_taken = 0
    if sent_at_str:
        try:
            sent_at = datetime.fromisoformat(sent_at_str)
            time_taken = int((datetime.utcnow() - sent_at).total_seconds())
        except (ValueError, TypeError):
            time_taken = 0

    service = QuizService(session)
    try:
        result = await service.submit_answer(
            session_id=session_id,
            question_index=index,
            selected_text=cb.data.removeprefix("ans:"),
            time_taken=time_taken,
        )
    except (QuizNotActiveError, QuizFinishedError):
        await state.clear()
        await cb.message.answer("Test yakunlandi.", reply_markup=reply.main_menu())
        await cb.answer()
        return

    await cb.answer()

    if result.is_last:
        await state.clear()
        try:
            await cb.message.delete()
        except Exception:
            await cb.message.edit_reply_markup(reply_markup=None)
        await _send_finish_and_menu(
            cb.message,
            score=result.score,
            total_questions=result.total_questions,
        )
        return

    await state.update_data(
        index=result.next_question.index,
        question_sent_at=datetime.utcnow().isoformat(),
    )
    if current_message_id:
        try:
            await bot.delete_message(cb.message.chat.id, current_message_id)
        except Exception:
            pass

    next_message = await cb.message.answer(
        _format_question(result.next_question),
        reply_markup=inline.quiz_keyboard(result.next_question),
        protect_content=True,
    )
    await state.update_data(question_message_id=next_message.message_id)

    # Schedule timeout for next question
    settings = await service.quiz.get_settings()
    if settings:
        _schedule_timeout(
            cb.from_user.id,
            bot,
            service,
            state,
            session_id,
            result.next_question.index,
            settings.time_limit_seconds,
            next_message.message_id,
        )


# ---------------------------------------------------------------
# QUIZ mode: native poll answer
# ---------------------------------------------------------------
@router.poll_answer()
async def handle_poll_answer(
    poll_answer: PollAnswer, session: AsyncSession, bot: Bot
) -> None:
    try:
        service = QuizService(session)
        mapping = await service.resolve_poll(poll_answer.poll_id)
        if not mapping:
            return

        # Cancel timeout if exists
        _cancel_timeout(poll_answer.user.id)

        import json
        options = json.loads(mapping.options_json)
        selected_idx = poll_answer.option_ids[0] if poll_answer.option_ids else -1
        selected_text = options[selected_idx] if 0 <= selected_idx < len(options) else ""

        # Calculate time taken from when poll was sent
        time_taken = int((datetime.utcnow() - mapping.sent_at).total_seconds()) if mapping.sent_at else 0

        try:
            result = await service.submit_answer(
                session_id=mapping.session_id,
                question_index=mapping.question_index,
                selected_text=selected_text,
                time_taken=time_taken,
            )
        except (QuizNotActiveError, QuizFinishedError):
            await service.delete_poll(poll_answer.poll_id)
            await bot.send_message(
                poll_answer.user.id, "Test yakunlandi.", reply_markup=reply.main_menu()
            )
            return

        await service.delete_poll(poll_answer.poll_id)

        # Delete the old poll message from chat - CRITICAL for auto-advance
        try:
            await bot.delete_message(poll_answer.user.id, mapping.message_id)
        except Exception as e:
            logger.warning(f"Failed to delete poll message {mapping.message_id}: {e}")

        if result.is_last:
            await bot.send_message(
                poll_answer.user.id,
                _finish_text(result.score, result.total_questions),
            )
            await bot.send_message(
                poll_answer.user.id,
                "Asosiy menyu:",
                reply_markup=reply.main_menu(),
            )
            return

        # Send next poll
        settings = await service.quiz.get_settings()
        time_limit = 40 if settings else 40  # Default to 40 seconds
        if settings:
            time_limit = settings.time_limit_seconds

        if result.next_question is None:
            logger.error(f"Next question is None for session {mapping.session_id}, index {mapping.question_index}")
            await bot.send_message(
                poll_answer.user.id,
                _finish_text(result.score, result.total_questions),
            )
            await bot.send_message(
                poll_answer.user.id,
                "Asosiy menyu:",
                reply_markup=reply.main_menu(),
            )
            return

        await _send_poll_question(
            bot=bot,
            chat_id=poll_answer.user.id,
            service=service,
            state=None,
            session_id=mapping.session_id,
            payload=result.next_question,
            time_limit=time_limit,
        )
    except Exception as e:
        logger.exception(f"Error in handle_poll_answer: {e}")


async def _send_poll_question(
    bot: Bot,
    chat_id: int,
    service: QuizService,
    state,
    session_id: int,
    payload: QuestionPayload,
    time_limit: int,
) -> None:
    try:
        # Safely truncate question text and sanitize
        question_text = payload.question.text[:295] if payload.question.text else "Savol noto'g'ri"
        poll_msg = await bot.send_poll(
            chat_id=chat_id,
            question=f"Savol {payload.index + 1}/{payload.total}\n{question_text}",
            options=payload.options,
            type="quiz",
            correct_option_id=payload.correct_option_index,
            is_anonymous=False,
            open_period=max(5, min(time_limit, 600)),
            protect_content=True,
        )
        await service.register_poll(
            poll_id=poll_msg.poll.id,
            message_id=poll_msg.message_id,
            sent_at=datetime.utcnow(),
            session_id=session_id,
            payload=payload,
        )

        # Schedule timeout for poll (QUIZ mode only)
        _schedule_timeout_poll(
            user_id=chat_id,
            bot=bot,
            service=service,
            poll_id=poll_msg.poll.id,
            session_id=session_id,
            message_id=poll_msg.message_id,
            time_limit=time_limit,
        )

        if state:
            await state.update_data(index=payload.index, question_sent_at=datetime.utcnow().isoformat())
    except Exception as e:
        logger.exception(f"Error sending poll question for session {session_id}: {e}")
