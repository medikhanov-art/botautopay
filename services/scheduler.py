import asyncio
from datetime import datetime
from sqlalchemy import select
from database.models import AsyncSessionLocal, Subscription
from config import CHANNEL_ID

async def check_subscriptions(bot):
    """Каждый час проверяет истёкшие подписки и кикает юзеров"""
    while True:
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            async with AsyncSessionLocal() as session:
                # Находим активные подписки, срок которых истек
                stmt = select(Subscription).where(
                    Subscription.status == "active",
                    Subscription.expires_at <= now_str
                )
                res = await session.execute(stmt)
                expired_subs = res.scalars().all()

                for sub in expired_subs:
                    try:
                        # Кикаем и сразу разбаниваем (чтобы юзер мог потом заново зайти по оплате)
                        await bot.ban_chat_member(chat_id=CHANNEL_ID, user_id=sub.customer_tg_id)
                        await bot.unban_chat_member(chat_id=CHANNEL_ID, user_id=sub.customer_tg_id)
                        
                        # Отправляем уведомление
                        await bot.send_message(
                            sub.customer_tg_id, 
                            "⚠️ Срок твоей подписки на закрытый канал истёк. Чтобы вернуться, продли подписку!"
                        )
                    except Exception as e:
                        print(f"Ошибка при кике {sub.customer_tg_id}: {e}")

                    # Обновляем статус в БД
                    sub.status = "expired"
                
                await session.commit()
                
        except Exception as e:
            print(f"Ошибка в фоновой проверке: {e}")

        # Спим 1 час (3600 секунд)
        await asyncio.sleep(3600)