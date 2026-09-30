from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db():
    Path("data/db").mkdir(parents=True, exist_ok=True)
    from app.models import User, Word, UserWord, Lesson, Answer  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight SQLite migration for databases created by older bot versions.
        columns = await conn.execute(text("PRAGMA table_info(words)"))
        word_columns = {row[1] for row in columns.fetchall()}
        if "category" not in word_columns:
            await conn.execute(text(
                "ALTER TABLE words ADD COLUMN category VARCHAR(50) NOT NULL DEFAULT 'irregular_verbs'"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_words_category ON words (category)"
            ))

        columns = await conn.execute(text("PRAGMA table_info(lessons)"))
        lesson_columns = {row[1] for row in columns.fetchall()}
        if "category" not in lesson_columns:
            await conn.execute(text(
                "ALTER TABLE lessons ADD COLUMN category VARCHAR(50) NOT NULL DEFAULT 'irregular_verbs'"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_lessons_category ON lessons (category)"
            ))
