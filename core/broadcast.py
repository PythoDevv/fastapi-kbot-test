"""Persistent, resumable broadcast engine shared by every bot.

The previous implementation ran the whole send loop inside the update handler
and kept nothing but two in-memory counters. That produced the "ko'pchilikka
bormadi" reports:

* a restart (deploy, crash, OOM, ``systemctl restart``) cancelled the loop
  mid-way — everyone after the cut-off silently got nothing and there was no
  record of where it stopped;
* only ``is_registered = True`` users were ever selected;
* a second 429 in a row dropped the user permanently;
* ``failed`` was a bare counter, so nobody could tell *who* missed the message,
  let alone re-send to them;
* the handler's DB session stayed open (idle in transaction) for the whole run.

This engine fixes all five: job state lives in the database, users are walked
by ascending ``users.id`` behind a persisted cursor, and the database is only
touched in short bursts between sends.

The engine is bot-agnostic — each bot passes its own prefixed models through
:class:`BroadcastModels`.
"""
from __future__ import annotations

import asyncio
import os
import socket
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
    TelegramUnauthorizedError,
)
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.logging import get_logger

logger = get_logger(__name__)


# --- job lifecycle ---------------------------------------------------------
JOB_PENDING = "pending"
JOB_RUNNING = "running"
JOB_DONE = "done"
JOB_FAILED = "failed"
JOB_CANCELLED = "cancelled"

RESUMABLE_STATUSES = (JOB_PENDING, JOB_RUNNING)

# --- per-recipient failure reasons ----------------------------------------
FAIL_BLOCKED = "blocked"      # user blocked the bot / deleted the account
FAIL_NOT_FOUND = "not_found"  # chat not found, bad target
FAIL_FLOOD = "flood"          # gave up after repeated 429s
FAIL_ERROR = "error"          # anything else

RETRY_CALLBACK_PREFIX = "bcast_retry"


@dataclass(frozen=True)
class BroadcastModels:
    """The three prefixed models a single bot contributes."""

    job: Any
    failure: Any
    user: Any


class BroadcastAborted(Exception):
    """A fault that would fail identically for every remaining recipient.

    Raising instead of counting the recipient as failed keeps the final report
    honest: the job stops with a reason rather than reporting thousands of
    "failures" that say nothing about the users.
    """


class SourceMessageGone(BroadcastAborted):
    """The admin deleted the message we were copying."""


@dataclass
class _RunState:
    """Counters buffered in memory between database flushes."""

    sent: int = 0
    failed: int = 0
    blocked: int = 0
    cursor_id: int = 0
    pending_failures: list[dict[str, Any]] = field(default_factory=list)
    blocked_ids: list[int] = field(default_factory=list)
    since_flush: int = 0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _humanize(seconds: float) -> str:
    total = int(seconds)
    if total < 60:
        return f"{total} soniya"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes} daqiqa {secs} soniya"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} soat {minutes} daqiqa"


class BroadcastEngine:
    """Runs one broadcast at a time per bot, resumably.

    Jobs are queued rather than run concurrently: two simultaneous loops would
    double the send rate and walk straight into Telegram's flood limit.
    """

    # Pause between two recipients. The real ceiling is the API round-trip
    # (~100-300ms), so this is a floor, not a target rate.
    SEND_DELAY = 0.05
    # How many user rows to pull per query.
    CHUNK_SIZE = 1000
    # Persist cursor + counters at least this often. Bounds how many recipients
    # can be sent twice if the process is killed without unwinding.
    FLUSH_EVERY = 20
    # Minimum gap between two edits of the admin's progress message.
    PROGRESS_INTERVAL = 30.0
    # Attempts per recipient before it is written off as a failure.
    MAX_ATTEMPTS = 5
    # Never sleep longer than this on a single 429.
    MAX_FLOOD_WAIT = 120
    # How long a process' claim on a job stays valid without a heartbeat.
    # Must comfortably exceed the flush interval, which is what renews it.
    LEASE_SECONDS = 300
    # If another process holds the lease, look again this many times before
    # leaving the job to them for good.
    MAX_CLAIM_RETRIES = 3

    def __init__(
        self,
        *,
        bot_key: str,
        models: BroadcastModels,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.bot_key = bot_key
        self._m = models
        self._session_factory = session_factory
        self._queue: asyncio.Queue[tuple[Bot, int]] = asyncio.Queue()
        self._queued: set[int] = set()
        self._worker: asyncio.Task[None] | None = None
        self._retry_tasks: set[asyncio.Task[None]] = set()
        self._claim_retries: dict[int, int] = {}
        # Set while no job is being sent — pause() waits on it.
        self._stopping = False
        self._idle = asyncio.Event()
        self._idle.set()
        # Identifies this process when claiming a job. Webhook and polling can
        # be running against the same database at the same time; without this
        # both would resume the same job and every user would get the message
        # twice.
        self._owner = f"{socket.gethostname()}:{os.getpid()}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def create_job(
        self,
        session: AsyncSession,
        *,
        admin_telegram_id: int,
        source_chat_id: int,
        source_message_id: int,
        status_chat_id: int | None = None,
        status_message_id: int | None = None,
        retry_of_job_id: int | None = None,
    ) -> int:
        """Persist a new job and return its id.

        Uses the caller's session so the row lands in the same transaction the
        handler middleware commits.
        """
        result = await session.execute(
            insert(self._m.job)
            .values(
                admin_telegram_id=admin_telegram_id,
                source_chat_id=source_chat_id,
                source_message_id=source_message_id,
                status=JOB_PENDING,
                status_chat_id=status_chat_id,
                status_message_id=status_message_id,
                retry_of_job_id=retry_of_job_id,
            )
            .returning(self._m.job.id)
        )
        return int(result.scalar_one())

    def enqueue(self, bot: Bot, job_id: int) -> None:
        """Schedule a job on the background worker (never blocks the handler)."""
        if job_id in self._queued or self._stopping:
            return
        self._queued.add(job_id)
        self._queue.put_nowait((bot, job_id))
        self._ensure_worker()

    async def pause(self, timeout: float = 20.0) -> None:
        """Park the running broadcast before the process exits.

        Called from the shutdown path of every entrypoint. Without it the DB
        engine and the bot session are torn down underneath a live send loop:
        the last few recipients are lost from the cursor, and the job's lease
        stays held by a pid that no longer exists — so a quick restart could
        not resume it until the lease timed out.
        """
        self._stopping = True
        if not self._idle.is_set():
            logger.info(
                "[%s] waiting for the running broadcast to park...", self.bot_key
            )
            try:
                await asyncio.wait_for(self._idle.wait(), timeout)
            except asyncio.TimeoutError:
                logger.warning(
                    "[%s] broadcast did not park within %ss — it will resume from "
                    "the last checkpoint instead",
                    self.bot_key, timeout,
                )
        self._cancel_background_tasks()

    def _cancel_background_tasks(self) -> None:
        for task in (self._worker, *self._retry_tasks):
            if task is not None and not task.done():
                task.cancel()
        self._retry_tasks.clear()
        self._worker = None

    async def resume_pending(self, bot: Bot) -> int:
        """Re-queue jobs left unfinished by a restart. Returns how many."""
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    select(self._m.job.id)
                    .where(self._m.job.status.in_(RESUMABLE_STATUSES))
                    .order_by(self._m.job.id)
                )
            ).scalars().all()
        for job_id in rows:
            self.enqueue(bot, int(job_id))
        if rows:
            logger.info(
                "[%s] resuming %d unfinished broadcast job(s): %s",
                self.bot_key, len(rows), list(rows),
            )
        return len(rows)

    async def cancel(self, job_id: int) -> bool:
        """Ask a queued or running job to stop. Returns True if it existed."""
        async with self._session_factory() as session:
            result = await session.execute(
                update(self._m.job)
                .where(
                    self._m.job.id == job_id,
                    self._m.job.status.in_(RESUMABLE_STATUSES),
                )
                .values(status=JOB_CANCELLED, finished_at=_utcnow())
            )
            await session.commit()
        return result.rowcount > 0

    # ------------------------------------------------------------------
    # Worker plumbing
    # ------------------------------------------------------------------
    def _ensure_worker(self) -> None:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(
                self._worker_loop(), name=f"broadcast-worker:{self.bot_key}"
            )

    async def _worker_loop(self) -> None:
        while True:
            bot, job_id = await self._queue.get()
            self._idle.clear()
            try:
                await self._run_job(bot, job_id)
            except asyncio.CancelledError:
                # Shutdown. The cursor is already persisted, so the next boot
                # picks the job up from where it stopped.
                logger.warning(
                    "[%s] broadcast job %d interrupted; will resume on restart",
                    self.bot_key, job_id,
                )
                raise
            except Exception:
                logger.exception(
                    "[%s] broadcast job %d crashed", self.bot_key, job_id
                )
            finally:
                self._queued.discard(job_id)
                self._idle.set()
                self._queue.task_done()

    def _schedule_claim_retry(self, bot: Bot, job_id: int) -> None:
        """Look at a job owned by someone else again once its lease could expire.

        Covers the SIGKILL case: the dead process' lease is still on the row,
        so the first claim fails, but LEASE_SECONDS later it is free.
        """
        attempts = self._claim_retries.get(job_id, 0)
        if attempts >= self.MAX_CLAIM_RETRIES or self._stopping:
            return
        self._claim_retries[job_id] = attempts + 1

        async def _later() -> None:
            await asyncio.sleep(self.LEASE_SECONDS)
            self.enqueue(bot, job_id)

        task = asyncio.create_task(_later(), name=f"broadcast-claim-retry:{job_id}")
        self._retry_tasks.add(task)
        task.add_done_callback(self._retry_tasks.discard)

    # ------------------------------------------------------------------
    # Job execution
    # ------------------------------------------------------------------
    async def _run_job(self, bot: Bot, job_id: int) -> None:
        job = await self._load_job(job_id)
        if job is None:
            logger.warning("[%s] broadcast job %d vanished", self.bot_key, job_id)
            return
        if job.status in (JOB_DONE, JOB_CANCELLED, JOB_FAILED):
            return
        if not await self._claim(job_id):
            # Another process (webhook vs. polling, or a second polling run) is
            # already working this job. Leaving it alone is the whole point.
            logger.warning(
                "[%s] broadcast job %d is owned by another process — skipping",
                self.bot_key, job_id,
            )
            self._schedule_claim_retry(bot, job_id)
            return

        started = time.monotonic()
        await self._set_running(job_id)

        if job.total:
            total = job.total  # Resumed job — keep the number the admin saw.
        else:
            total = await self._count_targets(job)
            await self._patch_job(job_id, total=total)

        state = _RunState(
            sent=job.sent or 0,
            failed=job.failed or 0,
            blocked=job.blocked or 0,
            cursor_id=job.cursor_id or 0,
        )
        # Back-dated so the admin's "navbatga qo'yildi" message turns into a
        # live counter on the very first recipient.
        last_progress = started - self.PROGRESS_INTERVAL

        try:
            while True:
                rows = await self._fetch_chunk(job, state.cursor_id)
                if not rows:
                    break
                for row_id, telegram_id in rows:
                    reason, detail = await self._deliver(bot, job, int(telegram_id))
                    if reason is None:
                        state.sent += 1
                    else:
                        state.failed += 1
                        state.pending_failures.append(
                            {
                                "job_id": job_id,
                                "telegram_id": int(telegram_id),
                                "reason": reason,
                                "detail": detail,
                            }
                        )
                        if reason == FAIL_BLOCKED:
                            state.blocked += 1
                            state.blocked_ids.append(int(telegram_id))

                    state.cursor_id = int(row_id)
                    state.since_flush += 1
                    if state.since_flush >= self.FLUSH_EVERY:
                        if self._stopping:
                            # Graceful shutdown: checkpoint and hand the job
                            # back so the next start resumes it immediately.
                            await self._flush(
                                job_id, state, status=JOB_PENDING, release=True
                            )
                            logger.info(
                                "[%s] broadcast job %d parked at %d/%d — resumes "
                                "on next start",
                                self.bot_key, job_id, state.sent + state.failed, total,
                            )
                            return
                        # Also renews this process' lease on the job.
                        await self._flush(job_id, state)
                        # Cancellation is checked on the flush boundary so a
                        # stop costs one extra query per 20 sends, not per send.
                        if await self._is_cancelled(job_id):
                            await self._report(
                                bot, job, state, total, started, JOB_CANCELLED
                            )
                            return

                    now = time.monotonic()
                    if now - last_progress >= self.PROGRESS_INTERVAL:
                        last_progress = now
                        await self._update_progress(bot, job, state, total)

                    await asyncio.sleep(self.SEND_DELAY)

            await self._flush(job_id, state)
            await self._report(bot, job, state, total, started, JOB_DONE)

        except BroadcastAborted as exc:
            await self._flush(job_id, state)
            await self._report(
                bot, job, state, total, started, JOB_FAILED, error=str(exc)
            )
        except asyncio.CancelledError:
            # Best effort: park the job as resumable, and drop the lease so the
            # next process to boot can pick it up without waiting it out.
            try:
                await asyncio.shield(
                    self._flush(job_id, state, status=JOB_PENDING, release=True)
                )
            except Exception:
                logger.exception("[%s] could not park job %d", self.bot_key, job_id)
            raise

    async def _deliver(
        self, bot: Bot, job: Any, telegram_id: int
    ) -> tuple[str | None, str | None]:
        """Send to one recipient. Returns (failure_reason, detail); (None, None) on success."""
        last_detail: str | None = None

        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                await bot.copy_message(
                    chat_id=telegram_id,
                    from_chat_id=job.source_chat_id,
                    message_id=job.source_message_id,
                )
                return None, None

            except TelegramRetryAfter as exc:
                # Telegram's flood wait. Honour it and try again — the old code
                # gave up after one retry and lost whole clusters of users.
                wait = min(exc.retry_after + 1, self.MAX_FLOOD_WAIT)
                last_detail = f"flood wait {exc.retry_after}s"
                logger.warning(
                    "[%s] flood wait %ss (attempt %d/%d)",
                    self.bot_key, exc.retry_after, attempt, self.MAX_ATTEMPTS,
                )
                await asyncio.sleep(wait)

            except TelegramForbiddenError as exc:
                return FAIL_BLOCKED, str(exc)[:500]

            except TelegramBadRequest as exc:
                text = str(exc).lower()
                if "message to copy not found" in text or "message_id_invalid" in text:
                    # The source message is gone; every remaining send would
                    # fail the same way. Stop instead of burning the whole list.
                    raise SourceMessageGone(str(exc)) from exc
                return FAIL_NOT_FOUND, str(exc)[:500]

            except (TelegramNetworkError, TelegramServerError) as exc:
                last_detail = str(exc)[:500]
                await asyncio.sleep(min(2 ** attempt, 30))

            except TelegramUnauthorizedError as exc:
                # A bad/revoked token fails identically for every recipient;
                # writing off the whole list one by one would report thousands
                # of "failures" that have nothing to do with the users.
                raise BroadcastAborted(f"bot token rad etildi: {exc}") from exc

            except TelegramAPIError as exc:
                return FAIL_ERROR, str(exc)[:500]

        return FAIL_FLOOD, last_detail

    # ------------------------------------------------------------------
    # Target selection
    # ------------------------------------------------------------------
    def _is_retry(self, job: Any) -> bool:
        return bool(getattr(job, "retry_of_job_id", None))

    def targets_stmt(self, job: Any, cursor_id: int) -> Any:
        """``(row_id, telegram_id)`` for the next slice of recipients.

        No filtering whatsoever on a normal job: every row in ``users`` is a
        recipient. Not ``is_registered`` (people who never finished sign-up
        still get the message), and not ``is_blocked`` either — that flag is
        recorded for reporting only, because a user who blocked the bot last
        month may well have unblocked it since.

        Ordering by the primary key is what makes ``cursor_id`` an exact resume
        point rather than an approximation.
        """
        user = self._m.user
        failure = self._m.failure
        if self._is_retry(job):
            return (
                select(failure.id, failure.telegram_id)
                .where(
                    failure.job_id == job.retry_of_job_id,
                    failure.reason != FAIL_BLOCKED,
                    failure.id > cursor_id,
                )
                .order_by(failure.id)
                .limit(self.CHUNK_SIZE)
            )
        return (
            select(user.id, user.telegram_id)
            .where(user.id > cursor_id)
            .order_by(user.id)
            .limit(self.CHUNK_SIZE)
        )

    def count_targets_stmt(self, job: Any) -> Any:
        user = self._m.user
        failure = self._m.failure
        if self._is_retry(job):
            return (
                select(func.count())
                .select_from(failure)
                .where(
                    failure.job_id == job.retry_of_job_id,
                    failure.reason != FAIL_BLOCKED,
                )
            )
        return select(func.count()).select_from(user)

    async def _count_targets(self, job: Any) -> int:
        async with self._session_factory() as session:
            return int(
                (await session.execute(self.count_targets_stmt(job))).scalar_one()
            )

    async def _fetch_chunk(self, job: Any, cursor_id: int) -> list[tuple[int, int]]:
        async with self._session_factory() as session:
            rows = (await session.execute(self.targets_stmt(job, cursor_id))).all()
        return [(int(r[0]), int(r[1])) for r in rows]

    # ------------------------------------------------------------------
    # Persistence helpers — every one opens and closes its own short session
    # so no connection is ever held idle-in-transaction across the send loop.
    # ------------------------------------------------------------------
    async def _load_job(self, job_id: int) -> Any | None:
        async with self._session_factory() as session:
            return await session.get(self._m.job, job_id)

    async def _set_running(self, job_id: int) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(self._m.job)
                .where(self._m.job.id == job_id)
                .values(status=JOB_RUNNING, started_at=_utcnow())
            )
            await session.commit()

    async def _patch_job(self, job_id: int, **values: Any) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(self._m.job).where(self._m.job.id == job_id).values(**values)
            )
            await session.commit()

    async def _is_cancelled(self, job_id: int) -> bool:
        # Cheap: only consulted once per chunk boundary in practice because the
        # status column is tiny and the row is hot in Postgres' buffer cache.
        async with self._session_factory() as session:
            status = (
                await session.execute(
                    select(self._m.job.status).where(self._m.job.id == job_id)
                )
            ).scalar_one_or_none()
        return status == JOB_CANCELLED

    def _owner_is_gone(self, locked_by: str | None) -> bool:
        """True when the lease belongs to a process on this host that has exited.

        A SIGKILL/SIGTERM never runs the shutdown path, so the dead process'
        lease stays on the row. On a single server — which is how these bots
        run — we can simply ask the OS whether that pid still exists, and take
        the job over on restart instead of waiting the lease out.
        """
        if not locked_by:
            return True
        host, _, pid = locked_by.rpartition(":")
        if host != socket.gethostname() or not pid.isdigit():
            return False  # another machine: only the timeout can free it
        try:
            os.kill(int(pid), 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False  # alive, just owned by another user
        return False

    async def _claim(self, job_id: int) -> bool:
        """Take (or renew) this process' exclusive lease on a job.

        Succeeds only if nobody holds it, the holder is us, its lease went
        stale, or the holder is a dead process on this host — so two live
        processes sharing the database can never send the same broadcast twice.
        """
        job = self._m.job
        cutoff = _utcnow() - timedelta(seconds=self.LEASE_SECONDS)
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(job.locked_by, job.locked_at).where(job.id == job_id)
                )
            ).first()
            if row is None:
                return False
            locked_by, locked_at = row

            takeable = (
                locked_by is None
                or locked_by == self._owner
                or (locked_at is not None and locked_at < cutoff)
                or self._owner_is_gone(locked_by)
            )
            if not takeable:
                return False

            # Compare-and-swap on what we just read: whoever writes first moves
            # locked_at, so a second claimer racing us finds no matching row.
            result = await session.execute(
                update(job)
                .where(
                    job.id == job_id,
                    job.locked_by.is_(None)
                    if locked_by is None
                    else job.locked_by == locked_by,
                    job.locked_at.is_(None)
                    if locked_at is None
                    else job.locked_at == locked_at,
                )
                .values(locked_by=self._owner, locked_at=_utcnow())
            )
            await session.commit()
        return result.rowcount == 1

    async def _flush(
        self,
        job_id: int,
        state: _RunState,
        status: str | None = None,
        release: bool = False,
    ) -> None:
        """Write buffered counters, failures and blocked flags in one go."""
        async with self._session_factory() as session:
            if state.pending_failures:
                await session.execute(insert(self._m.failure), state.pending_failures)
            if state.blocked_ids:
                await session.execute(
                    update(self._m.user)
                    .where(self._m.user.telegram_id.in_(state.blocked_ids))
                    .values(is_blocked=True)
                )
            values: dict[str, Any] = {
                "sent": state.sent,
                "failed": state.failed,
                "blocked": state.blocked,
                "cursor_id": state.cursor_id,
                # Doubles as the lease heartbeat.
                "locked_at": None if release else _utcnow(),
            }
            if release:
                values["locked_by"] = None
            if status is not None:
                values["status"] = status
            await session.execute(
                update(self._m.job).where(self._m.job.id == job_id).values(**values)
            )
            await session.commit()
        state.pending_failures.clear()
        state.blocked_ids.clear()
        state.since_flush = 0

    async def _finish(self, job_id: int, status: str, error: str | None = None) -> None:
        values: dict[str, Any] = {
            "status": status,
            "finished_at": _utcnow(),
            "locked_by": None,
            "locked_at": None,
        }
        if error:
            values["error"] = error[:1000]
        await self._patch_job(job_id, **values)

    # ------------------------------------------------------------------
    # Admin feedback
    # ------------------------------------------------------------------
    async def _update_progress(
        self, bot: Bot, job: Any, state: _RunState, total: int
    ) -> None:
        if not job.status_chat_id or not job.status_message_id:
            return
        done = state.sent + state.failed
        percent = int(done * 100 / total) if total else 0
        text = (
            "📤 <b>Reklama yuborilmoqda...</b>\n\n"
            f"Jami: <b>{total}</b>\n"
            f"Yuborildi: <b>{state.sent}</b>\n"
            f"Yetib bormadi: <b>{state.failed}</b>\n"
            f"Bajarildi: <b>{percent}%</b>"
        )
        await self._safe_edit(bot, job, text)

    async def _report(
        self,
        bot: Bot,
        job: Any,
        state: _RunState,
        total: int,
        started: float,
        status: str,
        error: str | None = None,
    ) -> None:
        await self._finish(job.id, status, error)

        heading = {
            JOB_DONE: "✅ <b>Reklama yakunlandi</b>",
            JOB_CANCELLED: "🛑 <b>Reklama to'xtatildi</b>",
            JOB_FAILED: "⚠️ <b>Reklama uzildi</b>",
        }[status]

        lines = [
            heading,
            "",
            f"Jami: <b>{total}</b>",
            f"Yuborildi: <b>{state.sent}</b>",
            f"Yetib bormadi: <b>{state.failed}</b>",
        ]
        if state.blocked:
            lines.append(f"    ↳ botni bloklaganlar: <b>{state.blocked}</b>")
        lines.append(f"Davomiyligi: <b>{_humanize(time.monotonic() - started)}</b>")
        if error:
            lines += ["", f"❗️ {error[:300]}"]
        lines += ["", f"<code>job #{job.id}</code>"]

        markup = None
        if state.failed:
            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔁 Yetib bormaganlarga qayta yuborish",
                            callback_data=f"{RETRY_CALLBACK_PREFIX}:{job.id}",
                        )
                    ]
                ]
            )

        await self._safe_edit(bot, job, "\n".join(lines), markup)
        logger.info(
            "[%s] broadcast job %d %s — total=%d sent=%d failed=%d blocked=%d",
            self.bot_key, job.id, status, total, state.sent, state.failed,
            state.blocked,
        )

    async def _safe_edit(
        self,
        bot: Bot,
        job: Any,
        text: str,
        markup: InlineKeyboardMarkup | None = None,
    ) -> None:
        if not job.status_chat_id or not job.status_message_id:
            return
        try:
            await bot.edit_message_text(
                chat_id=job.status_chat_id,
                message_id=job.status_message_id,
                text=text,
                reply_markup=markup,
            )
        except TelegramBadRequest as exc:
            if "not modified" not in str(exc).lower():
                logger.debug("[%s] progress edit failed: %s", self.bot_key, exc)
        except TelegramAPIError as exc:
            logger.debug("[%s] progress edit failed: %s", self.bot_key, exc)
