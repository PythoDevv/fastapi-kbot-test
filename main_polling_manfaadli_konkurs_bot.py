import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bots.Manfaadli_konkurs_bot.handlers.router import build_router
from bots.Manfaadli_konkurs_bot.models import User as Manfaadli_konkurs_botUser
from bots.Manfaadli_konkurs_bot.repositories import UserRepository as Manfaadli_konkurs_botUserRepo
from bots.Manfaadli_konkurs_bot.services.broadcast_service import engine as broadcast_engine
from core.admin_init import initialize_admins
from core.config import settings
from core.database import AsyncSessionLocal, dispose_engine
from core.logging import get_logger, setup_logging
from core.middleware import DbSessionMiddleware

setup_logging()
logger = get_logger(__name__)


async def main() -> None:
    if not settings.MANFAADLI_KONKURS_BOT_BOT_TOKEN:
        raise RuntimeError("MANFAADLI_KONKURS_BOT_BOT_TOKEN is not configured")

    bot = Bot(
        token=settings.MANFAADLI_KONKURS_BOT_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp["admin_ids"] = settings.MANFAADLI_KONKURS_BOT_ADMIN_IDS
    dp["bot_name"] = "manfaadli_konkurs_bot"
    dp.update.middleware(DbSessionMiddleware(AsyncSessionLocal))
    dp.include_router(build_router())

    async with AsyncSessionLocal() as session:
        await initialize_admins(
            session,
            settings.MANFAADLI_KONKURS_BOT_ADMIN_IDS,
            Manfaadli_konkurs_botUser,
            Manfaadli_konkurs_botUserRepo,
        )

    await bot.delete_webhook(drop_pending_updates=False)
    me = await bot.get_me()
    logger.info("Manfaadli_konkurs_bot polling started: @%s", me.username)

    # Pick up any broadcast a previous restart cut off mid-run.
    await broadcast_engine.resume_pending(bot)

    try:
        allowed_updates = list(dp.resolve_used_update_types())
        if "poll_answer" not in allowed_updates:
            allowed_updates.append("poll_answer")
        await dp.start_polling(bot, allowed_updates=allowed_updates)
    finally:
        # Park any running broadcast before the bot session and the DB engine
        # are torn down underneath it.
        await broadcast_engine.pause()
        await bot.session.close()
        await dispose_engine()
        logger.info("Manfaadli_konkurs_bot polling stopped.")


if __name__ == "__main__":
    asyncio.run(main())
