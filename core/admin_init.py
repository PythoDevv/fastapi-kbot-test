"""Admin initialization on bot startup."""
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.models import User
from bots.kitobxon.repositories import UserRepository
from core.logging import get_logger

logger = get_logger(__name__)


async def initialize_admins(session: AsyncSession, admin_ids: list[int]) -> None:
    """
    Ensure that all admin_ids are marked as admin in the database.
    If user doesn't exist, create them as admin.
    If user exists, ensure is_admin=True.
    """
    if not admin_ids:
        return

    repo = UserRepository(session)

    for admin_id in admin_ids:
        user = await repo.get_by_telegram_id(admin_id)

        if user is None:
            # Create new admin user
            user = User(
                telegram_id=admin_id,
                is_admin=True,
                is_registered=True,
                step=0,
            )
            session.add(user)
            logger.info("Created new admin user: %d", admin_id)
        elif not user.is_admin:
            # Update existing user to admin
            user.is_admin = True
            logger.info("Promoted user %d to admin", admin_id)
        else:
            logger.debug("User %d is already admin", admin_id)

    await session.commit()
    logger.info("Admin initialization complete. Admin IDs: %s", admin_ids)
