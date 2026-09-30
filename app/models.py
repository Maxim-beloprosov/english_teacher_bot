from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Bangkok")
    daily_new_words: Mapped[int] = mapped_column(Integer, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user_words: Mapped[list["UserWord"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    lessons: Mapped[list["Lesson"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Word(Base):
    __tablename__ = "words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    infinitive: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    past_simple: Mapped[str] = mapped_column(String(100), default="")
    past_participle: Mapped[str] = mapped_column(String(100), default="")
    translation: Mapped[str] = mapped_column(String(255))
    example: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(50), default="irregular_verbs", index=True)

    user_words: Mapped[list["UserWord"]] = relationship(back_populates="word")


class UserWord(Base):
    __tablename__ = "user_words"
    __table_args__ = (UniqueConstraint("user_id", "word_id", name="uq_user_word"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id"), index=True)

    seen_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    interval_days: Mapped[int] = mapped_column(Integer, default=1)
    next_review: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    mastered: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="user_words")
    word: Mapped["Word"] = relationship(back_populates="user_words")


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category: Mapped[str] = mapped_column(String(50), default="irregular_verbs", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_questions: Mapped[int] = mapped_column(Integer, default=0)
    correct_answers: Mapped[int] = mapped_column(Integer, default=0)
    wrong_answers: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="lessons")


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), index=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id"), index=True)
    question_type: Mapped[str] = mapped_column(String(50))
    selected: Mapped[str] = mapped_column(String(255))
    correct: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
