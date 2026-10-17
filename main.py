import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from database.models import init_db
from handlers.user import router as user_router
from services.scheduler import check_subscriptions
from handlers.saas import router as saas_router

logging.basicConfig(level=logging.INFO)

async def main():
    # Инициализируем базу данных
    await init_db()
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # Регистрируем роутер
    dp.include_router(user_router)

    # Регистрируем роутер для SaaS
    dp.include_router(saas_router)

    # Запускаем фоновую проверку подписок
    asyncio.create_task(check_subscriptions(bot))

    print("🚀 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())