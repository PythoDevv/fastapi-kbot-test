"""Per-recipient delivery rules of the broadcast engine.

The old implementation retried a flood-waited recipient exactly once and then
wrote them off, which is how whole clusters of users silently missed a
broadcast. These tests pin the replacement behaviour.
"""
import unittest

from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)

from core.broadcast import (
    FAIL_BLOCKED,
    FAIL_FLOOD,
    FAIL_NOT_FOUND,
    BroadcastEngine,
    BroadcastModels,
    SourceMessageGone,
)


class _Method:
    """Stand-in for the aiogram method object the exceptions want."""

    def __init__(self) -> None:
        self.model_config = {}


def _retry_after(seconds: int) -> TelegramRetryAfter:
    return TelegramRetryAfter(
        method=_Method(), message="Too Many Requests", retry_after=seconds
    )


def _bad_request(message: str) -> TelegramBadRequest:
    return TelegramBadRequest(method=_Method(), message=message)


def _forbidden(message: str) -> TelegramForbiddenError:
    return TelegramForbiddenError(method=_Method(), message=message)


class FakeBot:
    """Replays a scripted sequence of outcomes for copy_message."""

    def __init__(self, script: list) -> None:
        self._script = list(script)
        self.calls = 0

    async def copy_message(self, **kwargs) -> None:
        self.calls += 1
        outcome = self._script.pop(0) if self._script else None
        if isinstance(outcome, Exception):
            raise outcome


class FakeJob:
    id = 1
    source_chat_id = 100
    source_message_id = 200
    retry_of_job_id = None


def _engine() -> BroadcastEngine:
    engine = BroadcastEngine(
        bot_key="test",
        models=BroadcastModels(job=None, failure=None, user=None),
        session_factory=None,  # type: ignore[arg-type]
    )
    engine.MAX_FLOOD_WAIT = 0  # do not actually sleep in tests
    return engine


class DeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_successful_send_reports_no_failure(self) -> None:
        bot = FakeBot([None])
        reason, _ = await _engine()._deliver(bot, FakeJob(), 555)
        self.assertIsNone(reason)
        self.assertEqual(bot.calls, 1)

    async def test_repeated_flood_waits_are_retried_until_success(self) -> None:
        # Two 429s in a row used to lose this user for good.
        bot = FakeBot([_retry_after(1), _retry_after(1), None])
        reason, _ = await _engine()._deliver(bot, FakeJob(), 555)
        self.assertIsNone(reason)
        self.assertEqual(bot.calls, 3)

    async def test_endless_flood_gives_up_after_max_attempts(self) -> None:
        engine = _engine()
        bot = FakeBot([_retry_after(1)] * (engine.MAX_ATTEMPTS + 3))
        reason, _ = await engine._deliver(bot, FakeJob(), 555)
        self.assertEqual(reason, FAIL_FLOOD)
        self.assertEqual(bot.calls, engine.MAX_ATTEMPTS)

    async def test_network_error_is_retried(self) -> None:
        bot = FakeBot([TelegramNetworkError(method=_Method(), message="boom"), None])
        engine = _engine()
        engine.MAX_ATTEMPTS = 3
        reason, _ = await engine._deliver(bot, FakeJob(), 555)
        self.assertIsNone(reason)
        self.assertEqual(bot.calls, 2)

    async def test_blocked_user_is_classified_not_retried(self) -> None:
        bot = FakeBot([_forbidden("bot was blocked by the user")])
        reason, detail = await _engine()._deliver(bot, FakeJob(), 555)
        self.assertEqual(reason, FAIL_BLOCKED)
        self.assertEqual(bot.calls, 1)
        self.assertIn("blocked", detail)

    async def test_unknown_chat_is_a_plain_failure(self) -> None:
        bot = FakeBot([_bad_request("chat not found")])
        reason, _ = await _engine()._deliver(bot, FakeJob(), 555)
        self.assertEqual(reason, FAIL_NOT_FOUND)

    async def test_deleted_source_message_aborts_the_whole_job(self) -> None:
        # Every remaining recipient would fail identically — stop instead of
        # burning through the entire user list.
        bot = FakeBot([_bad_request("message to copy not found")])
        with self.assertRaises(SourceMessageGone):
            await _engine()._deliver(bot, FakeJob(), 555)


if __name__ == "__main__":
    unittest.main()
