import asyncio
import importlib
from types import SimpleNamespace

import pytest


BOTS = ["Kitobmillatbot", "Millatchiroqlaribot"]


class FakeUsers:
    def __init__(self, users):
        self.users = users
        self.top_by_score_calls = 0

    async def top_by_score(self, limit):
        self.top_by_score_calls += 1
        return self.users[:limit]

    async def top_by_referrals(self, limit):
        sorted_users = sorted(
            [user for user in self.users if getattr(user, "is_registered", True)],
            key=lambda user: (-(user.referrals_count or 0), user.id),
        )
        return sorted_users[:limit]

    async def get_by_telegram_id(self, telegram_id):
        return next(
            (user for user in self.users if user.telegram_id == telegram_id),
            None,
        )

    async def referral_rank(self, telegram_id):
        sorted_users = sorted(
            [user for user in self.users if getattr(user, "is_registered", True)],
            key=lambda user: (-(user.referrals_count or 0), user.id),
        )
        for index, user in enumerate(sorted_users, start=1):
            if user.telegram_id == telegram_id:
                return index
        return None


class FakeQuiz:
    async def get_top_latest_completed_sessions(self, limit):
        raise AssertionError("Score leaderboard must use users.score, not test sessions")


@pytest.mark.parametrize("bot", BOTS)
def test_results_leaderboard_uses_user_score(bot):
    module = importlib.import_module(f"bots.{bot}.services.results_service")
    service = module.ResultsService.__new__(module.ResultsService)
    service.users = FakeUsers(
        [
            SimpleNamespace(telegram_id=935795577, fio="Ilyos", username="ilyosbek_kv", score=101),
            SimpleNamespace(telegram_id=222, fio="Ali", username="ali", score=80),
        ]
    )
    service.quiz = FakeQuiz()

    entries = asyncio.run(service.top_test_takers(935795577, limit=30))

    assert service.users.top_by_score_calls == 1
    assert entries[0].is_current is True
    assert entries[0].value == 101


@pytest.mark.parametrize("bot", BOTS)
def test_referral_leaderboard_appends_current_user_outside_limit(bot):
    module = importlib.import_module(f"bots.{bot}.services.results_service")
    service = module.ResultsService.__new__(module.ResultsService)
    service.users = FakeUsers(
        [
            SimpleNamespace(
                id=index,
                telegram_id=10_000 + index,
                fio=f"User {index}",
                username=None,
                score=0,
                referrals_count=100 - index,
                is_registered=True,
            )
            for index in range(1, 31)
        ]
        + [
            SimpleNamespace(
                id=99,
                telegram_id=935795577,
                fio="Ilyos",
                username="ilyosbek_kv",
                score=0,
                referrals_count=1,
                is_registered=True,
            )
        ]
    )
    service.quiz = FakeQuiz()

    entries = asyncio.run(service.top_by_referrals(935795577, limit=30))

    assert len(entries) == 31
    assert entries[-1].is_current is True
    assert entries[-1].rank == 31
    assert entries[-1].value == 1
