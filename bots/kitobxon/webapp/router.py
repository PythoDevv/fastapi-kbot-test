from collections.abc import AsyncGenerator
from datetime import datetime
from functools import lru_cache

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.exceptions import (
    AlreadySolvedError,
    QuizFinishedError,
    QuizNotActiveError,
    QuizWaitingError,
)
from bots.kitobxon.services import QuizService
from bots.kitobxon.webapp.auth import (
    get_token_from_header,
    verify_init_data_and_issue_token,
    verify_token,
)
from bots.kitobxon.webapp.schemas import (
    AnswerRequest,
    AnswerResponse,
    AuthRequest,
    AuthResponse,
    QuestionOut,
    StartResponse,
)
from core.config import settings
from core.database import AsyncSessionLocal
from core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/webapp", tags=["webapp"])


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


def _q_out(payload) -> QuestionOut:
    return QuestionOut(
        index=payload.index,
        text=payload.question.text,
        options=payload.options,
    )


def _format_total_time(seconds: int) -> str:
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}m {secs}s"


@lru_cache(maxsize=1)
def _get_bot() -> Bot:
    return Bot(
        token=settings.KITOBXON_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


@lru_cache(maxsize=1)
def _load_webapp_html() -> str:
    import os

    html_path = os.path.join(
        os.path.dirname(__file__),
        "../../../static/webapp/index.html",
    )
    html_path = os.path.abspath(html_path)
    with open(html_path, encoding="utf-8") as f:
        return f.read()


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def webapp_index(request: Request):
    return HTMLResponse(_load_webapp_html())


@router.post("/auth", response_model=AuthResponse)
async def auth(body: AuthRequest):
    telegram_id, token = verify_init_data_and_issue_token(
        body.init_data,
        settings.KITOBXON_BOT_TOKEN,
        settings.WEBAPP_JWT_SECRET,
    )
    return AuthResponse(token=token)


@router.post("/start", response_model=StartResponse)
async def start_quiz(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    token = get_token_from_header(authorization)
    telegram_id = verify_token(token, settings.WEBAPP_JWT_SECRET)

    service = QuizService(db)
    try:
        result = await service.resume_or_start_session(telegram_id)
    except QuizWaitingError:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="waiting")
    except QuizFinishedError:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="finished")
    except AlreadySolvedError:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="already_solved")

    return StartResponse(
        session_id=result.session.id,
        question=_q_out(result.first_question),
        total=result.session.total_questions,
        time_limit_seconds=result.settings.time_limit_seconds,
    )


@router.post("/answer", response_model=AnswerResponse)
async def submit_answer(
    body: AnswerRequest,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    token = get_token_from_header(authorization)
    telegram_id = verify_token(token, settings.WEBAPP_JWT_SECRET)

    service = QuizService(db)
    is_timeout = body.selected_option is None
    time_taken_sec = max(0, body.time_taken_ms // 1000)

    try:
        result = await service.submit_answer(
            session_id=body.session_id,
            question_index=body.question_index,
            selected_text=body.selected_option or "",
            time_taken=time_taken_sec,
            is_timeout=is_timeout,
        )
        response_session_id = body.session_id
    except (QuizNotActiveError, QuizFinishedError) as e:
        detail = str(e)
        if isinstance(e, QuizNotActiveError) and detail == "Session topilmadi":
            recovered = await service.resume_or_start_session(telegram_id)
            return AnswerResponse(
                session_id=recovered.session.id,
                score=recovered.session.score,
                is_last=False,
                next_question=_q_out(recovered.first_question),
                total_questions=recovered.session.total_questions,
                total_time_seconds=0,
            )
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=detail)

    if result.is_last:
        try:
            await _get_bot().send_message(
                telegram_id,
                "🧑‍💻 WebApp test yakunlandi.\n\n"
                f"Natija: <b>{result.score}/{result.total_questions}</b>\n"
                f"Sarflagan vaqt: <b>{_format_total_time(result.total_time_seconds)}</b>",
            )
        except Exception:
            logger.exception("Failed to send WebApp result message user=%s", telegram_id)

    return AnswerResponse(
        session_id=response_session_id,
        score=result.score,
        is_last=result.is_last,
        next_question=_q_out(result.next_question) if result.next_question else None,
        total_questions=result.total_questions,
        total_time_seconds=result.total_time_seconds,
    )
