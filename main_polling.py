"""
Polling fallback mode.
Use this when webhook is unreachable or during a contest peak load.

Usage:
    python main_polling.py

This shares the same database as the webhook mode.
Stop the webhook service first to avoid double processing:
    sudo systemctl stop kbot
"""
import asyncio

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bots.kitobxon.handlers.router import build_router
from bots.kitobxon.models import User as KitobxonUser
from bots.kitobxon.repositories import UserRepository as KitobxonUserRepo
from bots.kitobxon.services.broadcast_service import engine as broadcast_engine
from core.config import settings
from core.database import AsyncSessionLocal, dispose_engine
from core.logging import get_logger, setup_logging
from core.middleware import DbSessionMiddleware
from core.admin_init import initialize_admins

setup_logging()
logger = get_logger(__name__)


async def main() -> None:
    bot = Bot(
        token=settings.KITOBXON_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp["admin_ids"] = settings.KITOBXON_ADMIN_IDS
    dp["bot_name"] = "kitobxon"
    dp.update.middleware(DbSessionMiddleware(AsyncSessionLocal))
    dp.include_router(build_router())

    # Initialize default admin users for polling startup too
    async with AsyncSessionLocal() as session:
        await initialize_admins(
            session,
            settings.KITOBXON_ADMIN_IDS,
            KitobxonUser,
            KitobxonUserRepo,
        )

    # Drop webhook so Telegram sends updates to polling
    await bot.delete_webhook(drop_pending_updates=False)
    me = await bot.get_me()
    logger.info("Polling mode started: @%s", me.username)

    # Pick up any broadcast a previous restart cut off mid-run.
    await broadcast_engine.resume_pending(bot)

    try:
        allowed_updates = list(dp.resolve_used_update_types())
        # Ensure poll_answer updates are allowed
        if "poll_answer" not in allowed_updates:
            allowed_updates.append("poll_answer")
        await dp.start_polling(bot, allowed_updates=allowed_updates)
    finally:
        # Park any running broadcast before the bot session and the DB engine
        # are torn down underneath it.
        await broadcast_engine.pause()
        await bot.session.close()
        await dispose_engine()
        logger.info("Polling stopped.")


if __name__ == "__main__":
    asyncio.run(main())
