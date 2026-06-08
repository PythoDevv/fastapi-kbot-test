"""Unit tests for the referral-award logic shared by all three bots.

These tests use a fake repository, so they run with no database — they verify
the two bugs that were fixed:

  1. The notification name comes from the registered FIO, never the new user's
     Telegram profile name (which produced ".." / foreign-script names).
  2. The bonus is awarded exactly once and the displayed count is the fresh,
     atomically-incremented value (no duplicated "Referallar soni").

Run:  ./venv/bin/python -m pytest tests/test_referral_award.py -v
"""

import asyncio
import importlib
from types import SimpleNamespace

import pytest

BOTS = ["Kitobmillatbot", "kitobxon", "Millatchiroqlaribot"]


def _load(bot_name):
    mod = importlib.import_module(f"bots.{bot_name}.services.auth_service")
    return mod.AuthService, mod.ReferralAward


class FakeUsers:
    """In-memory stand-in for UserRepository with the same award contract."""

    def __init__(self, new_user, referrer):
        self.new_user = new_user
        self.referrer = referrer
        self.increment_referrals_calls = 0
        self.increment_score_calls = 0

    async def get_by_telegram_id(self, telegram_id):
        if telegram_id == self.new_user.telegram_id:
            return self.new_user
        if self.referrer and telegram_id == self.referrer.telegram_id:
            return self.referrer
        return None

    async def claim_referral_bonus(self, telegram_id):
        # Mirrors the atomic conditional UPDATE: only the first caller wins.
        if self.new_user.referral_bonus_awarded:
            return False
        self.new_user.referral_bonus_awarded = True
        return True

    async def increment_score(self, user_id, delta):
        self.increment_score_calls += 1
        self.referrer.score += delta

    async def increment_referrals(self, user_id, delta=1):
        self.increment_referrals_calls += 1
        self.referrer.referrals_count += delta
        return self.referrer.referrals_count


def _make_service(bot_name, new_user, referrer):
    AuthService, ReferralAward = _load(bot_name)
    service = AuthService(session=None)
    service.users = FakeUsers(new_user, referrer)
    return service, ReferralAward


def _user(telegram_id, *, fio=None, username=None, referred_by=None, awarded=False):
    return SimpleNamespace(
        id=telegram_id,
        telegram_id=telegram_id,
        fio=fio,
        username=username,
        referred_by=referred_by,
        referral_bonus_awarded=awarded,
        referrals_count=0,
        score=0,
    )


@pytest.mark.parametrize("bot", BOTS)
def test_name_comes_from_registered_fio(bot):
    referrer = _user(100)
    referrer.referrals_count = 2
    new_user = _user(200, fio="Dilbar Xakimova", username="tg_handle", referred_by=100)
    service, _ = _make_service(bot, new_user, referrer)

    award = asyncio.run(service.award_referral_bonus_if_eligible(200))

    assert award is not None
    assert award.new_user_name == "Dilbar Xakimova"
    assert award.referrer_telegram_id == 100


@pytest.mark.parametrize("bot", BOTS)
def test_name_falls_back_to_username_then_default(bot):
    referrer = _user(100)
    # fio missing -> username
    nu = _user(200, fio=None, username="onlyhandle", referred_by=100)
    service, _ = _make_service(bot, nu, referrer)
    award = asyncio.run(service.award_referral_bonus_if_eligible(200))
    assert award.new_user_name == "onlyhandle"

    # fio and username missing -> safe default, never "None"/".."
    referrer2 = _user(101)
    nu2 = _user(201, fio=None, username=None, referred_by=101)
    service2, _ = _make_service(bot, nu2, referrer2)
    award2 = asyncio.run(service2.award_referral_bonus_if_eligible(201))
    assert award2.new_user_name == "Foydalanuvchi"


@pytest.mark.parametrize("bot", BOTS)
def test_returns_fresh_incremented_count(bot):
    referrer = _user(100)
    referrer.referrals_count = 2
    new_user = _user(200, fio="X", referred_by=100)
    service, _ = _make_service(bot, new_user, referrer)

    award = asyncio.run(service.award_referral_bonus_if_eligible(200))

    assert award.referrals_count == 3  # 2 -> 3, the value produced by THIS award
    assert referrer.referrals_count == 3


@pytest.mark.parametrize("bot", BOTS)
def test_double_award_is_blocked(bot):
    referrer = _user(100)
    referrer.referrals_count = 2
    new_user = _user(200, fio="X", referred_by=100)
    service, _ = _make_service(bot, new_user, referrer)

    first = asyncio.run(service.award_referral_bonus_if_eligible(200))
    second = asyncio.run(service.award_referral_bonus_if_eligible(200))

    assert first is not None
    assert second is None  # atomic claim refuses the second time
    assert referrer.referrals_count == 3  # incremented exactly once
    assert service.users.increment_referrals_calls == 1


@pytest.mark.parametrize("bot", BOTS)
def test_no_referrer_link_returns_none(bot):
    new_user = _user(200, fio="X", referred_by=None)
    service, _ = _make_service(bot, new_user, referrer=None)
    award = asyncio.run(service.award_referral_bonus_if_eligible(200))
    assert award is None
