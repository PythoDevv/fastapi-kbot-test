import asyncio
from dataclasses import dataclass
from typing import Any, Callable

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bots.kitobxon.handlers.router import build_router as build_kitobxon_router
from bots.kitobxon.models import User as KitobxonUser
from bots.kitobxon.repositories import UserRepository as KitobxonUserRepo
from bots.Kitobmillatbot.handlers.router import build_router as build_kitobmillatbot_router
from bots.Kitobmillatbot.models import User as KitobmillatbotUser
from bots.Kitobmillatbot.repositories import UserRepository as KitobmillatbotUserRepo
from bots.Millatchiroqlaribot.handlers.router import build_router as build_millatchiroqlaribot_router
from bots.Millatchiroqlaribot.models import User as MillatchiroqlaribotUser
from bots.Millatchiroqlaribot.repositories import UserRepository as MillatchiroqlaribotUserRepo
from bots.Barakali_tanlov_bot.handlers.router import build_router as build_barakali_tanlov_bot_router
from bots.Barakali_tanlov_bot.models import User as BarakaliTanlovBotUser
from bots.Barakali_tanlov_bot.repositories import UserRepository as BarakaliTanlovBotUserRepo
from core.admin_init import initialize_admins
from core.config import settings
from core.database import AsyncSessionLocal, dispose_engine
from core.logging import get_logger, setup_logging
from core.middleware import DbSessionMiddleware

setup_logging()
logger = get_logger(__name__)


@dataclass(frozen=True)
class PollingBotSpec:
    name: str
    token: str
    admin_ids: list[int]
    router_builder: Callable[[], Router]
    user_model: Any
    user_repo: Any


async def _run_polling_bot(spec: PollingBotSpec) -> None:
    bot = Bot(
        token=spec.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp["admin_ids"] = spec.admin_ids
    dp["bot_name"] = spec.name
    dp.update.middleware(DbSessionMiddleware(AsyncSessionLocal))
    dp.include_router(spec.router_builder())

    try:
        async with AsyncSessionLocal() as session:
            await initialize_admins(
                session,
                spec.admin_ids,
                spec.user_model,
                spec.user_repo,
            )

        await bot.delete_webhook(drop_pending_updates=False)
        me = await bot.get_me()
        logger.info("%s polling started: @%s", spec.name, me.username)

        allowed_updates = list(dp.resolve_used_update_types())
        if "poll_answer" not in allowed_updates:
            allowed_updates.append("poll_answer")
        await dp.start_polling(bot, allowed_updates=allowed_updates)
    finally:
        await bot.session.close()
        logger.info("%s polling stopped.", spec.name)


def _build_specs() -> list[PollingBotSpec]:
    specs: list[PollingBotSpec] = []
    if settings.KITOBXON_MODE == "polling":
        specs.append(
            PollingBotSpec(
                name="kitobxon",
                token=settings.KITOBXON_BOT_TOKEN,
                admin_ids=settings.KITOBXON_ADMIN_IDS,
                router_builder=build_kitobxon_router,
                user_model=KitobxonUser,
                user_repo=KitobxonUserRepo,
            )
        )
    if settings.KITOBMILLATBOT_BOT_TOKEN and settings.KITOBMILLATBOT_MODE == "polling":
        specs.append(
            PollingBotSpec(
                name="kitobmillatbot",
                token=settings.KITOBMILLATBOT_BOT_TOKEN,
                admin_ids=settings.KITOBMILLATBOT_ADMIN_IDS,
                router_builder=build_kitobmillatbot_router,
                user_model=KitobmillatbotUser,
                user_repo=KitobmillatbotUserRepo,
            )
        )
    if settings.MILLATCHIROQLARIBOT_BOT_TOKEN and settings.MILLATCHIROQLARIBOT_MODE == "polling":
        specs.append(
            PollingBotSpec(
                name="millatchiroqlaribot",
                token=settings.MILLATCHIROQLARIBOT_BOT_TOKEN,
                admin_ids=settings.MILLATCHIROQLARIBOT_ADMIN_IDS,
                router_builder=build_millatchiroqlaribot_router,
                user_model=MillatchiroqlaribotUser,
                user_repo=MillatchiroqlaribotUserRepo,
            )
        )
    if settings.BARAKALI_TANLOV_BOT_BOT_TOKEN and settings.BARAKALI_TANLOV_BOT_MODE == "polling":
        specs.append(
            PollingBotSpec(
                name="barakali_tanlov_bot",
                token=settings.BARAKALI_TANLOV_BOT_BOT_TOKEN,
                admin_ids=settings.BARAKALI_TANLOV_BOT_ADMIN_IDS,
                router_builder=build_barakali_tanlov_bot_router,
                user_model=BarakaliTanlovBotUser,
                user_repo=BarakaliTanlovBotUserRepo,
            )
        )
    return specs


async def main() -> None:
    specs = _build_specs()
    if not specs:
        raise RuntimeError("No bots are configured with MODE=polling")

    logger.info(
        "Starting polling bots: %s",
        ", ".join(spec.name for spec in specs),
    )

    try:
        await asyncio.gather(*(_run_polling_bot(spec) for spec in specs))
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
