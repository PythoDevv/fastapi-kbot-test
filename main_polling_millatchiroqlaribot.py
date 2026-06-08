import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bots.Millatchiroqlaribot.handlers.router import build_router
from bots.Millatchiroqlaribot.models import User as MillatchiroqlaribotUser
from bots.Millatchiroqlaribot.repositories import UserRepository as MillatchiroqlaribotUserRepo
from core.admin_init import initialize_admins
from core.config import settings
from core.database import AsyncSessionLocal, dispose_engine
from core.logging import get_logger, setup_logging
from core.middleware import DbSessionMiddleware

setup_logging()
logger = get_logger(__name__)


async def main() -> None:
    if not settings.MILLATCHIROQLARIBOT_BOT_TOKEN:
        raise RuntimeError("MILLATCHIROQLARIBOT_BOT_TOKEN is not configured")

    bot = Bot(
        token=settings.MILLATCHIROQLARIBOT_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp["admin_ids"] = settings.MILLATCHIROQLARIBOT_ADMIN_IDS
    dp["bot_name"] = "millatchiroqlaribot"
    dp.update.middleware(DbSessionMiddleware(AsyncSessionLocal))
    dp.include_router(build_router())

    async with AsyncSessionLocal() as session:
        await initialize_admins(
            session,
            settings.MILLATCHIROQLARIBOT_ADMIN_IDS,
            MillatchiroqlaribotUser,
            MillatchiroqlaribotUserRepo,
        )

    await bot.delete_webhook(drop_pending_updates=False)
    me = await bot.get_me()
    logger.info("Millatchiroqlaribot polling started: @%s", me.username)

    try:
        allowed_updates = list(dp.resolve_used_update_types())
        if "poll_answer" not in allowed_updates:
            allowed_updates.append("poll_answer")
        await dp.start_polling(bot, allowed_updates=allowed_updates)
    finally:
        await bot.session.close()
        await dispose_engine()
        logger.info("Millatchiroqlaribot polling stopped.")


if __name__ == "__main__":
    asyncio.run(main())
