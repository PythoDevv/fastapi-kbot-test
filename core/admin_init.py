"""Admin initialization on bot startup."""
from typing import TYPE_CHECKING, Type

from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger

if TYPE_CHECKING:
    from bots.kitobxon.models import User as UserType
    from bots.kitobxon.repositories import UserRepository as UserRepoType

logger = get_logger(__name__)


async def initialize_admins(
    session: AsyncSession,
    admin_ids: list[int],
    user_model: "Type[UserType]",
    user_repo_class: "Type[UserRepoType]",
) -> None:
    if not admin_ids:
        return

    repo = user_repo_class(session)

    for admin_id in admin_ids:
        user = await repo.get_by_telegram_id(admin_id)

        if user is None:
            user = user_model(
                telegram_id=admin_id,
                is_admin=True,
                is_registered=True,
                step=0,
            )
            session.add(user)
            logger.info("Created new admin user: %d", admin_id)
        elif not user.is_admin:
            user.is_admin = True
            logger.info("Promoted user %d to admin", admin_id)
        else:
            logger.debug("User %d is already admin", admin_id)

    await session.commit()
    logger.info("Admin initialization complete. Admin IDs: %s", admin_ids)
