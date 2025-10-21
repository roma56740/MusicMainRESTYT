import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
from handlers import register
from handlers import start, booking, social, location  
from db import init_db
from handlers import referral
from notifier import check_bookings_loop  # ⏰ фоновая проверка записей

# Загрузка .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
    
async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )

    # Создание базы данных
    init_db()

    # Инициализация бота
    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Подключение роутеров
    dp.include_router(start.router)
    dp.include_router(booking.router)
    dp.include_router(register.router)
    dp.include_router(social.router)
    dp.include_router(location.router)
    dp.include_router(referral.router)

    # Запуск фона: уведомления и подтверждения
    asyncio.create_task(check_bookings_loop(bot))

    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
