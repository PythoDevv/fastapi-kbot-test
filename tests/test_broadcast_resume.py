"""The broadcast must survive a restart.

Regression for the "ko'pchilikka bormadi" reports: the previous implementation
ran the send loop inside the update handler with two in-memory counters, so a
deploy or crash mid-run silently dropped every user after the cut-off, with no
record of where it stopped.

These tests drive the real ``_run_job`` loop against an in-memory stand-in for
the job tables, so cursor handling, resume, failure recording and cancellation
are exercised exactly as they run in production.
"""
import asyncio
import unittest
from types import SimpleNamespace

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from core.broadcast import (
    FAIL_BLOCKED,
    FAIL_NOT_FOUND,
    JOB_CANCELLED,
    JOB_DONE,
    JOB_PENDING,
    JOB_RUNNING,
    BroadcastEngine,
    BroadcastModels,
)

USER_COUNT = 25
FLUSH_EVERY = 5


class _Method:
    def __init__(self) -> None:
        self.model_config = {}


class ScriptedBot:
    """Records recipients; can fail for specific users or die mid-run."""

    def __init__(self, *, forbidden=(), not_found=(), die_after=None) -> None:
        self.received: list[int] = []
        self._forbidden = set(forbidden)
        self._not_found = set(not_found)
        self._die_after = die_after

    async def copy_message(self, *, chat_id: int, **kwargs) -> None:
        if self._die_after is not None and len(self.received) >= self._die_after:
            # Stands in for SIGTERM / OOM arriving mid-loop.
            raise asyncio.CancelledError
        if chat_id in self._forbidden:
            raise TelegramForbiddenError(
                method=_Method(), message="bot was blocked by the user"
            )
        if chat_id in self._not_found:
            raise TelegramBadRequest(method=_Method(), message="chat not found")
        self.received.append(chat_id)


class InMemoryEngine(BroadcastEngine):
    """Real send loop, fake persistence."""

    def __init__(self, users: list[tuple[int, int]]) -> None:
        super().__init__(
            bot_key="test",
            models=BroadcastModels(job=None, failure=None, user=None),
            session_factory=None,  # type: ignore[arg-type]
        )
        self.SEND_DELAY = 0
        self.FLUSH_EVERY = FLUSH_EVERY
        self.PROGRESS_INTERVAL = 10**9
        self.MAX_FLOOD_WAIT = 0

        self.users = users
        self.failures: list[dict] = []
        self.blocked: set[int] = set()
        self.cancelled = False
        self.claimable = True
        self.released = False
        self.reports: list[str] = []
        self.job = SimpleNamespace(
            id=1,
            status=JOB_PENDING,
            total=0,
            sent=0,
            failed=0,
            blocked=0,
            cursor_id=0,
            source_chat_id=1,
            source_message_id=2,
            retry_of_job_id=None,
            status_chat_id=None,
            status_message_id=None,
            error=None,
            started_at=None,
            finished_at=None,
        )

    # --- persistence stand-ins ---------------------------------------
    async def _load_job(self, job_id):
        return self.job

    async def _set_running(self, job_id) -> None:
        self.job.status = JOB_RUNNING

    async def _patch_job(self, job_id, **values) -> None:
        for key, value in values.items():
            setattr(self.job, key, value)

    async def _is_cancelled(self, job_id) -> bool:
        return self.cancelled

    async def _count_targets(self, job):
        return len(self.users)

    async def _claim(self, job_id) -> bool:
        return self.claimable

    async def _fetch_chunk(self, job, cursor_id):
        # No filtering: a user who blocked the bot is still a recipient.
        return [(uid, tid) for uid, tid in self.users if uid > cursor_id][
            : self.CHUNK_SIZE
        ]

    async def _flush(self, job_id, state, status=None, release=False) -> None:
        self.released = release
        self.failures.extend(state.pending_failures)
        self.blocked.update(state.blocked_ids)
        self.job.sent = state.sent
        self.job.failed = state.failed
        self.job.blocked = state.blocked
        self.job.cursor_id = state.cursor_id
        if status is not None:
            self.job.status = status
        state.pending_failures.clear()
        state.blocked_ids.clear()
        state.since_flush = 0

    async def _safe_edit(self, bot, job, text, markup=None) -> None:
        self.reports.append(text)


def _users(count: int = USER_COUNT) -> list[tuple[int, int]]:
    # (users.id, telegram_id) — registration status is irrelevant by design.
    return [(i, 1000 + i) for i in range(1, count + 1)]


class ResumeTests(unittest.IsolatedAsyncioTestCase):
    async def test_a_clean_run_reaches_every_user_once(self) -> None:
        engine = InMemoryEngine(_users())
        bot = ScriptedBot()

        await engine._run_job(bot, 1)

        self.assertEqual(sorted(bot.received), [t for _, t in _users()])
        self.assertEqual(engine.job.sent, USER_COUNT)
        self.assertEqual(engine.job.failed, 0)
        self.assertEqual(engine.job.status, JOB_DONE)

    async def test_a_crash_parks_the_job_as_resumable(self) -> None:
        engine = InMemoryEngine(_users())
        bot = ScriptedBot(die_after=13)

        with self.assertRaises(asyncio.CancelledError):
            await engine._run_job(bot, 1)

        self.assertEqual(engine.job.status, JOB_PENDING)
        self.assertEqual(engine.job.cursor_id, 13)
        self.assertEqual(len(bot.received), 13)

    async def test_resume_delivers_exactly_the_remaining_users(self) -> None:
        engine = InMemoryEngine(_users())
        first = ScriptedBot(die_after=13)
        with self.assertRaises(asyncio.CancelledError):
            await engine._run_job(first, 1)

        second = ScriptedBot()
        await engine._run_job(second, 1)

        self.assertEqual(sorted(first.received + second.received),
                         [t for _, t in _users()])
        self.assertEqual(engine.job.sent, USER_COUNT)
        self.assertEqual(engine.job.status, JOB_DONE)

    async def test_hard_kill_loses_no_user_even_with_a_stale_cursor(self) -> None:
        """A SIGKILL skips the tidy-up, so the cursor is only as fresh as the
        last flush. Nobody may be *missed*; a few repeats are the accepted cost."""
        engine = InMemoryEngine(_users())
        first = ScriptedBot(die_after=13)
        with self.assertRaises(asyncio.CancelledError):
            await engine._run_job(first, 1)

        # Rewind to the last FLUSH_EVERY boundary, as an unclean kill would.
        engine.job.cursor_id = (13 // FLUSH_EVERY) * FLUSH_EVERY
        engine.job.sent = engine.job.cursor_id

        second = ScriptedBot()
        await engine._run_job(second, 1)

        delivered = first.received + second.received
        self.assertEqual(set(delivered), {t for _, t in _users()})
        duplicates = len(delivered) - len(set(delivered))
        self.assertLessEqual(duplicates, FLUSH_EVERY)

    async def test_failures_are_recorded_per_recipient(self) -> None:
        engine = InMemoryEngine(_users())
        bot = ScriptedBot(forbidden={1003}, not_found={1007})

        await engine._run_job(bot, 1)

        by_id = {f["telegram_id"]: f["reason"] for f in engine.failures}
        self.assertEqual(by_id, {1003: FAIL_BLOCKED, 1007: FAIL_NOT_FOUND})
        self.assertEqual(engine.job.failed, 2)
        self.assertEqual(engine.job.sent, USER_COUNT - 2)
        self.assertEqual(engine.job.blocked, 1)
        # The 403 is recorded on the user for reporting...
        self.assertIn(1003, engine.blocked)
        # ...but a plain delivery error says nothing about the user.
        self.assertNotIn(1007, engine.blocked)

    async def test_a_previous_block_never_excludes_a_user(self) -> None:
        """A block can be undone, and Telegram is the only source of truth —
        so the flag is reporting metadata, never a send-time filter."""
        engine = InMemoryEngine(_users())
        await engine._run_job(ScriptedBot(forbidden={1003}), 1)
        self.assertIn(1003, engine.blocked)

        engine.job.cursor_id = 0
        engine.job.sent = engine.job.failed = engine.job.blocked = 0
        engine.job.total = 0
        engine.job.status = JOB_PENDING
        second = ScriptedBot()  # they unblocked the bot in the meantime
        await engine._run_job(second, 1)

        self.assertIn(1003, second.received)
        self.assertEqual(len(second.received), USER_COUNT)

    async def test_a_job_owned_by_another_process_is_left_alone(self) -> None:
        """Webhook and polling may run against one database; only the process
        holding the lease may send, otherwise every user gets it twice."""
        engine = InMemoryEngine(_users())
        engine.claimable = False
        bot = ScriptedBot()

        await engine._run_job(bot, 1)

        self.assertEqual(bot.received, [])
        self.assertEqual(engine.job.status, JOB_PENDING)

    async def test_graceful_shutdown_parks_the_job_and_frees_the_lease(self) -> None:
        """Ctrl+C in polling: the loop must checkpoint and let go of the job
        before the DB engine is disposed, so a restart resumes it at once."""
        engine = InMemoryEngine(_users())

        class StoppingBot(ScriptedBot):
            async def copy_message(self, **kwargs):
                await super().copy_message(**kwargs)
                if len(self.received) == FLUSH_EVERY:
                    engine._stopping = True

        bot = StoppingBot()
        await engine._run_job(bot, 1)

        self.assertEqual(engine.job.status, JOB_PENDING)
        self.assertEqual(engine.job.cursor_id, FLUSH_EVERY)
        self.assertEqual(len(bot.received), FLUSH_EVERY)
        self.assertTrue(engine.released, "the lease must be handed back")

    async def test_pause_returns_immediately_when_nothing_is_running(self) -> None:
        engine = InMemoryEngine(_users())
        await asyncio.wait_for(engine.pause(timeout=1.0), timeout=2.0)
        self.assertTrue(engine._stopping)
        # A late enqueue during shutdown must not start new work.
        engine.enqueue(ScriptedBot(), 99)
        self.assertNotIn(99, engine._queued)

    async def test_cancel_stops_the_run_and_keeps_the_counters(self) -> None:
        engine = InMemoryEngine(_users())
        engine.cancelled = True
        bot = ScriptedBot()

        await engine._run_job(bot, 1)

        self.assertEqual(engine.job.status, JOB_CANCELLED)
        # Stops on the first flush boundary, not after the whole list.
        self.assertEqual(len(bot.received), FLUSH_EVERY)
        self.assertEqual(engine.job.sent, FLUSH_EVERY)


if __name__ == "__main__":
    unittest.main()
