import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bots.Kitobmillatbot.handlers.router import build_router
from bots.Kitobmillatbot.models import User as KitobmillatbotUser
from bots.Kitobmillatbot.repositories import UserRepository as KitobmillatbotUserRepo
from core.admin_init import initialize_admins
from core.config import settings
from core.database import AsyncSessionLocal, dispose_engine
from core.logging import get_logger, setup_logging
from core.middleware import DbSessionMiddleware

setup_logging()
logger = get_logger(__name__)


async def main() -> None:
    if not settings.KITOBMILLATBOT_BOT_TOKEN:
        raise RuntimeError("KITOBMILLATBOT_BOT_TOKEN is not configured")

    bot = Bot(
        token=settings.KITOBMILLATBOT_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp["admin_ids"] = settings.KITOBMILLATBOT_ADMIN_IDS
    dp["bot_name"] = "kitobmillatbot"
    dp.update.middleware(DbSessionMiddleware(AsyncSessionLocal))
    dp.include_router(build_router())

    async with AsyncSessionLocal() as session:
        await initialize_admins(
            session,
            settings.KITOBMILLATBOT_ADMIN_IDS,
            KitobmillatbotUser,
            KitobmillatbotUserRepo,
        )

    await bot.delete_webhook(drop_pending_updates=False)
    me = await bot.get_me()
    logger.info("Kitobmillatbot polling started: @%s", me.username)

    try:
        allowed_updates = list(dp.resolve_used_update_types())
        if "poll_answer" not in allowed_updates:
            allowed_updates.append("poll_answer")
        await dp.start_polling(bot, allowed_updates=allowed_updates)
    finally:
        await bot.session.close()
        await dispose_engine()
        logger.info("Kitobmillatbot polling stopped.")


if __name__ == "__main__":
    asyncio.run(main())
