"""Per-bot wiring for the shared, resumable broadcast engine.

The send loop itself lives in :mod:`core.broadcast`; this module only binds it
to Millatchiroqlaribot's own prefixed tables and gives the handlers a small facade.
"""
from aiogram import Bot
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bots.Millatchiroqlaribot.models import BroadcastFailure, BroadcastJob, User
from core.broadcast import FAIL_BLOCKED, BroadcastEngine, BroadcastModels
from core.database import AsyncSessionLocal

# One engine per bot, shared by every handler and by the startup resume hook.
engine = BroadcastEngine(
    bot_key="millatchiroqlaribot",
    models=BroadcastModels(job=BroadcastJob, failure=BroadcastFailure, user=User),
    session_factory=AsyncSessionLocal,
)


class BroadcastService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def start(
        self,
        bot: Bot,
        *,
        admin_telegram_id: int,
        source_chat_id: int,
        source_message_id: int,
        status_chat_id: int,
        status_message_id: int,
        retry_of_job_id: int | None = None,
    ) -> int:
        """Persist the job, hand it to the worker, return immediately."""
        job_id = await engine.create_job(
            self.session,
            admin_telegram_id=admin_telegram_id,
            source_chat_id=source_chat_id,
            source_message_id=source_message_id,
            status_chat_id=status_chat_id,
            status_message_id=status_message_id,
            retry_of_job_id=retry_of_job_id,
        )
        # The worker reads the job through its own session, so the row has to be
        # committed before it is queued — waiting for the middleware's commit
        # would leave a window where the worker sees nothing.
        await self.session.commit()
        engine.enqueue(bot, job_id)
        return job_id

    async def get_job(self, job_id: int) -> BroadcastJob | None:
        return await self.session.get(BroadcastJob, job_id)

    async def count_retryable(self, job_id: int) -> int:
        """Recipients of ``job_id`` worth another attempt (blocked ones are not)."""
        stmt = (
            select(func.count())
            .select_from(BroadcastFailure)
            .where(
                BroadcastFailure.job_id == job_id,
                BroadcastFailure.reason != FAIL_BLOCKED,
            )
        )
        return int((await self.session.execute(stmt)).scalar_one())
