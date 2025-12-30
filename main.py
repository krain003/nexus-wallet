import asyncio
import sys
import os
import uvicorn
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
import structlog

from config.settings import settings
from database.connection import db_manager
from database.models import Base

# Import all handlers
from handlers import start_router, wallet_router, send_router, receive_router, swap_router, p2p_router, history_router, settings_router

# Import services to initialize
from services import price_service, swap_service

# Import API app for uvicorn
from api.server import app as fastapi_app

logger = structlog.get_logger()

# Global variable to manage uvicorn server task
server_task = None

async def on_startup(bot: Bot):
    bot_info = await bot.get_me()
    logger.info(f"Bot started: @{bot_info.username}")
    
    # Start web server in the background
    global server_task
    port = int(os.getenv("PORT", 8000))
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())
    logger.info(f"Web server started on port {port}")

async def on_shutdown(bot: Bot):
    logger.info("Shutting down...")
    if server_task:
        server_task.cancel()
    await price_service.close()
    await swap_service.close()
    await db_manager.close()

async def create_tables():
    async with db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("DB tables checked/created")

async def main():
    await db_manager.initialize()
    await create_tables()

    bot = Bot(token=settings.BOT_TOKEN.get_secret_value(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start_router)
    dp.include_router(wallet_router)
    dp.include_router(send_router)
    dp.include_router(receive_router)
    dp.include_router(swap_router)
    dp.include_router(p2p_router)
    dp.include_router(history_router)
    dp.include_router(settings_router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), drop_pending_updates=True)

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped manually.")