import os
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import BigInteger, String, Integer, ForeignKey

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "bot_database.sqlite")
engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}", echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)

class Channel(Base):
    __tablename__ = "channels"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, unique=True) # ID канала клиента
    title: Mapped[str] = mapped_column(String(255))                  # Название канала
    price_stars: Mapped[int] = mapped_column(Integer, default=50)    # Цена подписки

class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, index=True)  # К какому каналу подписка
    customer_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    expires_at: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="active")

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)