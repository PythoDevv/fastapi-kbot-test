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


def _format_question(payload: QuestionPayload) -> str:
    return (
        f"<b>Savol {payload.index + 1}/{payload.total}</b>\n\n"
        f"{payload.question.text}"
    )


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

    # Subscription check
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

    # Award referral bonus if user was referred and hasn't received bonus yet
    if (
        user.referred_by
        and not user.referral_bonus_awarded
    ):
        referrer = await user_repo.get_by_telegram_id(user.referred_by)
        if referrer:
            # Award 1 point to referrer
            await user_repo.increment_score(referrer.id, 1)
            # Mark that bonus was awarded
            await user_repo.update_fields(
                message.from_user.id, referral_bonus_awarded=True
            )

    service = QuizService(session)
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
        await message.answer("Sizda faol test mavjud. Uni davom ettiring.")
        return
    except KitobxonError as e:
        await message.answer(str(e))
        return

    await state.set_state(QuizStates.answering)
    await state.update_data(
        session_id=result.session.id,
        index=0,
        quiz_type=result.quiz_type.value,
    )

    if result.quiz_type == QuizType.WEB:
        await message.answer(
            _format_question(result.first_question),
            reply_markup=inline.quiz_keyboard(result.first_question),
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

    service = QuizService(session)
    try:
        result = await service.submit_answer(
            session_id=session_id,
            question_index=index,
            selected_text=cb.data.removeprefix("ans:"),
            time_taken=0,
        )
    except (QuizNotActiveError, QuizFinishedError):
        await state.clear()
        await cb.message.answer("Test yakunlandi.", reply_markup=reply.main_menu())
        await cb.answer()
        return

    await cb.answer("✅" if result.is_correct else "❌")

    if result.is_last:
        await state.clear()
        await cb.message.edit_reply_markup(reply_markup=None)
        await cb.message.answer(
            f"Test yakunlandi!\n\nNatija: <b>{result.score}/{result.total_questions}</b>",
            reply_markup=reply.main_menu(),
        )
        return

    await state.update_data(index=result.next_question.index)
    await cb.message.edit_text(
        _format_question(result.next_question),
        reply_markup=inline.quiz_keyboard(result.next_question),
    )


# ---------------------------------------------------------------
# QUIZ mode: native poll answer
# ---------------------------------------------------------------
@router.poll_answer()
async def handle_poll_answer(
    poll_answer: PollAnswer, session: AsyncSession, bot: Bot
) -> None:
    service = QuizService(session)
    mapping = await service.resolve_poll(poll_answer.poll_id)
    if not mapping:
        return

    import json
    options = json.loads(mapping.options_json)
    selected_idx = poll_answer.option_ids[0] if poll_answer.option_ids else -1
    selected_text = options[selected_idx] if 0 <= selected_idx < len(options) else ""

    try:
        result = await service.submit_answer(
            session_id=mapping.session_id,
            question_index=mapping.question_index,
            selected_text=selected_text,
            time_taken=0,
        )
    except (QuizNotActiveError, QuizFinishedError):
        await service.delete_poll(poll_answer.poll_id)
        await bot.send_message(
            poll_answer.user.id, "Test yakunlandi.", reply_markup=reply.main_menu()
        )
        return

    await service.delete_poll(poll_answer.poll_id)

    if result.is_last:
        await bot.send_message(
            poll_answer.user.id,
            f"Test yakunlandi!\n\nNatija: <b>{result.score}/{result.total_questions}</b>",
            reply_markup=reply.main_menu(),
        )
        return

    # Send next poll
    test_session = await service.quiz.get_session(mapping.session_id)
    time_limit = 30
    settings = await service.quiz.get_settings()
    if settings:
        time_limit = settings.time_limit_seconds

    await _send_poll_question(
        bot=bot,
        chat_id=poll_answer.user.id,
        service=service,
        state=None,
        session_id=mapping.session_id,
        payload=result.next_question,
        time_limit=time_limit,
    )


async def _send_poll_question(
    bot: Bot,
    chat_id: int,
    service: QuizService,
    state,
    session_id: int,
    payload: QuestionPayload,
    time_limit: int,
) -> None:
    poll_msg = await bot.send_poll(
        chat_id=chat_id,
        question=f"Savol {payload.index + 1}/{payload.total}\n{payload.question.text[:295]}",
        options=payload.options,
        type="quiz",
        correct_option_id=payload.correct_option_index,
        is_anonymous=False,
        open_period=max(5, min(time_limit, 600)),
    )
    await service.register_poll(
        poll_id=poll_msg.poll.id,
        session_id=session_id,
        payload=payload,
    )
    if state:
        await state.update_data(index=payload.index)
