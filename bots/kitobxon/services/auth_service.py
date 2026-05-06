from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.models import User
from bots.kitobxon.repositories import UserRepository


@dataclass
class RegistrationResult:
    user: User
    is_new: bool


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def touch_user(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
    ) -> RegistrationResult:
        user, created = await self.users.get_or_create(
            telegram_id=telegram_id,
            username=username,
            fio=first_name,
        )
        if not created and user.username != (username or "") and username:
            user.username = username
        return RegistrationResult(user=user, is_new=created)

    async def set_name(self, telegram_id: int, fio: str) -> User:
        fio = fio.strip()
        await self.users.update_fields(telegram_id, fio=fio)
        user = await self.users.get_by_telegram_id(telegram_id)
        assert user is not None
        return user

    async def set_phone(self, telegram_id: int, phone: str) -> User:
        await self.users.update_fields(
            telegram_id, mobile_number=phone.strip(), step=2
        )
        user = await self.users.get_by_telegram_id(telegram_id)
        assert user is not None
        return user

    async def mark_registered(self, telegram_id: int) -> None:
        await self.users.update_fields(telegram_id, is_registered=True, step=3)

    async def set_how_did_find(self, telegram_id: int, text: str) -> None:
        await self.users.update_fields(telegram_id, how_did_find=text[:255])

    async def apply_referral(
        self, new_user: User, referrer_telegram_id: int
    ) -> bool:
        """Applies a referral if valid. Returns True if applied."""
        if new_user.telegram_id == referrer_telegram_id:
            return False
        if new_user.referred_by:
            return False
        referrer = await self.users.get_by_telegram_id(referrer_telegram_id)
        if not referrer:
            return False
        new_user.referred_by = referrer_telegram_id
        await self.users.increment_referrals(referrer.id, 1)
        await self.session.flush()
        return True

    async def award_referral_bonus_if_eligible(self, telegram_id: int) -> bool:
        """Award 1 score point to the referrer exactly once."""
        user = await self.users.get_by_telegram_id(telegram_id)
        if not user or not user.referred_by or user.referral_bonus_awarded:
            return False

        referrer = await self.users.get_by_telegram_id(user.referred_by)
        if not referrer:
            return False

        await self.users.increment_score(referrer.id, 1)
        await self.users.update_fields(telegram_id, referral_bonus_awarded=True)
        return True
