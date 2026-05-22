from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

# SQLite — файл app.db на хосте
import os
DB_PATH = os.getenv("DB_PATH", "/app/data/app.db")
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

engine = create_async_engine(DATABASE_URL, echo=False)

# Фабрика сессий
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


async def get_db() -> AsyncSession:
    """Отдаёт сессию БД для каждого запроса."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Создать все таблицы (вызывается при запуске)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
