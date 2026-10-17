from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import LabeledPrice, PreCheckoutQuery
from datetime import datetime, timedelta
from sqlalchemy import select
from database.models import AsyncSessionLocal, User, Channel, Subscription
from config import CHANNEL_ID

router = Router()

# 1. Старт с поддержкой параметров (покупка для конкретного канала)
@router.message(CommandStart())
async def cmd_start(message: types.Message):
    args = message.text.split(maxsplit=1)
    
    # Сохраняем пользователя в БД
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.tg_id == message.from_user.id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        
        if not user:
            new_user = User(
                tg_id=message.from_user.id, 
                username=message.from_user.username
            )
            session.add(new_user)
            await session.commit()

    # Проверяем, перешел ли юзер по ссылке конкретного канала (например, /start ch_1606645486)
    target_channel = None
    if len(args) > 1 and args[1].startswith("ch_"):
        try:
            ch_db_id = int(args[1].split("_")[1])
            async with AsyncSessionLocal() as session:
                ch_res = await session.execute(select(Channel).where(Channel.channel_id == ch_db_id))
                target_channel = ch_res.scalar_one_or_none()
        except Exception:
            pass

    if target_channel:
        # Если покупают подписку на кастомный канал SaaS-клиента
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(
                text=f"⭐ Купить доступ ({target_channel.price_stars} Stars)", 
                callback_data=f"buy_ch_{target_channel.channel_id}"
            )]
        ])
        await message.answer(
            f"👋 Привет! Ты хочешь оформить подписку на закрытый канал:\n"
            f"📌 **{target_channel.title}**\n\n"
            f"💰 Стоимость: {target_channel.price_stars} Stars за 1 месяц.\n"
            "Жми кнопку ниже для оплаты!",
            reply_markup=kb
        )
    else:
        # Дефолтный вариант (если зашли просто в твоего главного бота)
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="⭐ Купить подписку (50 Stars)", callback_data="buy_default")]
        ])
        await message.answer(
            f"Привет, {message.from_user.first_name}! 👋\n\n"
            "Это платформа платных подписок в Telegram.",
            reply_markup=kb
        )

# 2. Обработка нажатия на кнопку покупки кастомного канала
@router.callback_query(F.data.startswith("buy_ch_"))
async def process_custom_channel_buy(callback: types.CallbackQuery):
    await callback.answer()
    ch_id = int(callback.data.split("_")[2])

    async with AsyncSessionLocal() as session:
        ch_res = await session.execute(select(Channel).where(Channel.channel_id == ch_id))
        channel = ch_res.scalar_one_or_none()

    if not channel:
        await callback.message.answer("❌ Ошибка: канал не найден или удален.")
        return

    prices = [LabeledPrice(label=f"Подписка на {channel.title}", amount=channel.price_stars)]
    
    # Payload будет содержать ID канала, чтобы при успешной оплате мы знали, куда выдать инвайт
    await callback.message.answer_invoice(
        title=f"Подписка: {channel.title}",
        description="Доступ на 30 дней",
        payload=f"sub_ch_{channel.channel_id}",
        currency="XTR",
        prices=prices,
    )

# 3. Дефолтная покупка (для твоего главного канала из .env)
@router.callback_query(F.data == "buy_default")
async def send_default_invoice(callback: types.CallbackQuery):
    await callback.answer()
    prices = [LabeledPrice(label="Подписка на 1 месяц", amount=50)]
    await callback.message.answer_invoice(
        title="Доступ в закрытый канал",
        description="Подписка на 30 дней",
        payload="sub_default",
        currency="XTR",
        prices=prices,
    )

@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

# 4. Успешный платёж (обрабатываем и дефолт, и SaaS-каналы)
@router.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    user_id = message.from_user.id
    payload = message.successful_payment.invoice_payload
    
    expire_date = datetime.now() + timedelta(days=30)
    expire_str = expire_date.strftime("%Y-%m-%d %H:%M:%S")

    # Определяем, для какого канала оформлена подписка
    target_channel_id = CHANNEL_ID # по умолчанию твой главный из .env
    
    if payload.startswith("sub_ch_"):
        try:
            target_channel_id = int(payload.split("_")[2])
        except Exception:
            pass

    # Сохраняем подписку в БД
    async with AsyncSessionLocal() as session:
        sub = Subscription(
            channel_id=target_channel_id,
            customer_tg_id=user_id,
            expires_at=expire_str,
            status="active"
        )
        session.add(sub)
        await session.commit()

    try:
        # Генерируем одноразовую инвайт-ссылку именно в тот канал, за который заплатили
        invite_link = await message.bot.create_chat_invite_link(
            chat_id=target_channel_id,
            member_limit=1,
            expire_date=datetime.now() + timedelta(hours=1)
        )

        await message.answer(
            f"🎉 **Оплата прошла успешно!**\n\n"
            f"Твоя подписка активна до: `{expire_str}`\n\n"
            f"Вот твоя персональная ссылка для входа в канал:\n{invite_link.invite_link}\n\n"
            f"⚠️ *Ссылка одноразовая и сгорит через 1 час!*"
        )
    except Exception as e:
        await message.answer("Оплата прошла, но возникла ошибка при создании ссылки. Обратись к администратору!")
        print(f"Error creating invite link for channel {target_channel_id}: {e}")

@router.message(Command("test_pay"))
async def test_payment_simulation(message: types.Message):
    user_id = message.from_user.id
    expire_date = datetime.now() + timedelta(days=30)
    expire_str = expire_date.strftime("%Y-%m-%d %H:%M:%S")

    # Сохраняем в БД как настоящий платёж
    async with AsyncSessionLocal() as session:
        sub = Subscription(
            customer_tg_id=user_id,
            expires_at=expire_str,
            status="active"
        )
        session.add(sub)
        await session.commit()

    try:
        # Генерируем тестовую одноразовую ссылку
        invite_link = await message.bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,
            expire_date=datetime.now() + timedelta(hours=1)
        )

        await message.answer(
            f"🧪 **[TEST MODE] Имитация успешной оплаты прошла!**\n\n"
            f"Подписка записана в БД до: `{expire_str}`\n"
            f"Ссылка для входа:\n{invite_link.invite_link}"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка проверки: {e}\nУбедись, что бот — админ в канале!")