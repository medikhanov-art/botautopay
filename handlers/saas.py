from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func
from database.models import AsyncSessionLocal, Channel, Subscription

router = Router()

# Состояния для добавления канала
class AddChannel(StatesGroup):
    waiting_for_channel = State()
    waiting_for_price = State()

# 1. Запуск добавления канала
@router.message(Command("addchannel"))
async def cmd_add_channel(message: types.Message, state: FSMContext):
    await message.answer(
        "📢 **Добавление нового канала в SaaS**\n\n"
        "1. Добавь моего бота в свой канал **администратором** (обязательно с правом создавать инвайт-ссылки).\n"
        "2. Перешли сюда **любое сообщение** из своего канала (или отправь его ID / юзернейм вроде `@my_channel`)."
    )
    await state.set_state(AddChannel.waiting_for_channel)

# 2. Получение канала и проверка прав бота
@router.message(AddChannel.waiting_for_channel)
async def process_channel_input(message: types.Message, state: FSMContext):
    channel_id = None
    channel_title = "Закрытый канал"

    # Если юзер переслал сообщение из канала
    if message.forward_from_chat:
        channel_id = message.forward_from_chat.id
        channel_title = message.forward_from_chat.title
    else:
        # Если ввел текстом (ID или юзернейм)
        try:
            text = message.text.strip()
            # Пробуем получить инфо о чате через бота
            chat = await message.bot.get_chat(text)
            if chat.type == "channel":
                channel_id = chat.id
                channel_title = chat.title
            else:
                await message.answer("❌ Это не канал! Попробуй еще раз или перешли сообщение из канала.")
                return
        except Exception:
            await message.answer("❌ Не удалось найти канал. Убедись, что бот добавлен в него администратором, и отправь ID (например, `-100...`) или перешли сообщение.")
            return

    # Проверяем, действительно ли бот админ в этом канале
    try:
        bot_member = await message.bot.get_chat_member(chat_id=channel_id, user_id=message.bot.id)
        if bot_member.status not in ["administrator", "creator"]:
            await message.answer("❌ Бот не является администратором в этом канале! Добавь его в админы и повтори попытку.")
            return
    except Exception as e:
        await message.answer(f"❌ Ошибка проверки прав: {e}. Убедись, что ID указан верно.")
        return

    # Сохраняем во временное состояние
    await state.update_data(channel_id=channel_id, title=channel_title)
    
    await message.answer(
        f"✅ Канал **«{channel_title}»** успешно распознан!\n\n"
        "Теперь введи **стоимость подписки за 1 месяц в Telegram Stars** (например: `50`):"
    )
    await state.set_state(AddChannel.waiting_for_price)

# 3. Получение цены и сохранение в БД
@router.message(AddChannel.waiting_for_price)
async def process_price_input(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Цена должна быть числом (в Stars). Попробуй еще раз:")
        return

    price = int(message.text)
    data = await state.get_data()
    channel_id = data["channel_id"]
    title = data["title"]
    owner_id = message.from_user.id

    # Записываем канал в базу данных
    async with AsyncSessionLocal() as session:
        # Проверим, не добавлен ли уже этот канал
        existing = await session.execute(select(Channel).where(Channel.channel_id == channel_id))
        if existing.scalar_one_or_none():
            await message.answer("⚠️ Этот канал уже зарегистрирован в системе!")
            await state.clear()
            return

        new_channel = Channel(
            owner_tg_id=owner_id,
            channel_id=channel_id,
            title=title,
            price_stars=price
        )
        session.add(new_channel)
        await session.commit()

    await state.clear()
    
    # Ссылка, по которой клиенты будут покупать подписку именно на этот канал
    bot_info = await message.bot.get_me()
    pay_link = f"https://t.me/{bot_info.username}?start=ch_{channel_id}"

    await message.answer(
        f"🎉 **Канал успешно подключен к SaaS!**\n\n"
        f"📌 Название: {title}\n"
        f"💰 Цена: {price} Stars / мес\n\n"
        f"🔗 **Ссылка для твоих покупателей:**\n{pay_link}\n\n"
        f"Управляй своими каналами через команду `/mychannels`."
    )

@router.message(Command("mychannels"))
async def cmd_my_channels(message: types.Message):
    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Channel).where(Channel.owner_tg_id == user_id))
        channels = result.scalars().all()

        if not channels:
            await message.answer("У тебя пока нет подключенных каналов. Используй `/addchannel`, чтобы добавить первый!")
            return

        text = "📊 **Твои подключенные каналы и статистика:**\n\n"
        for ch in channels:
            # Считаем количество активных подписчиков в этом канале
            subs_count = await session.scalar(
                select(func.count(Subscription.id)).where(
                    Subscription.channel_id == ch.channel_id,
                    Subscription.status == "active"
                )
            )
            text += f"🔹 **{ch.title}**\n"
            text += f"   • Цена: {ch.price_stars} Stars/мес\n"
            text += f"   • Активных подписчиков: {subs_count}\n"
            text += f"   • ID канала: `{ch.channel_id}`\n\n"

        await message.answer(text)