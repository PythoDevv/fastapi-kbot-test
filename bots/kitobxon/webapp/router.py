from collections.abc import AsyncGenerator
from datetime import datetime

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.exceptions import (
    AlreadySolvedError,
    QuizAlreadyStartedError,
    QuizFinishedError,
    QuizNotActiveError,
    QuizWaitingError,
)
from bots.kitobxon.repositories import UserRepository
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


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def webapp_index(request: Request):
    import os
    html_path = os.path.join(os.path.dirname(__file__), "../../../static/webapp/index.html")
    html_path = os.path.abspath(html_path)
    with open(html_path, encoding="utf-8") as f:
        return HTMLResponse(f.read())


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
        result = await service.start_session(telegram_id)
    except QuizAlreadyStartedError:
        user_repo = UserRepository(db)
        user = await user_repo.get_by_telegram_id(telegram_id)
        active = await service.quiz.get_active_session(user.id)
        payload = await service.get_current_payload(active.id)
        settings_obj = await service.quiz.get_settings()
        return StartResponse(
            session_id=active.id,
            question=_q_out(payload),
            total=active.total_questions,
            time_limit_seconds=settings_obj.time_limit_seconds,
        )
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
    verify_token(token, settings.WEBAPP_JWT_SECRET)

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
    except (QuizNotActiveError, QuizFinishedError) as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))

    return AnswerResponse(
        score=result.score,
        is_last=result.is_last,
        next_question=_q_out(result.next_question) if result.next_question else None,
        total_questions=result.total_questions,
    )
