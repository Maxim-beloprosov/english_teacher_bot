import random
from datetime import datetime, timedelta
from sqlalchemy import select, func
from app.db import SessionLocal
from app.models import User, Word, UserWord, Lesson, Answer


class LearningService:
    @staticmethod
    async def get_or_create_user(telegram_id: int, username: str | None):
        async with SessionLocal() as session:
            user = (await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )).scalar_one_or_none()
            if not user:
                user = User(telegram_id=telegram_id, username=username)
                session.add(user)
                await session.commit()
                await session.refresh(user)
            else:
                user.username = username
                await session.commit()
            return user

    @staticmethod
    async def create_lesson(user_id: int, new_count: int, category: str):
        now = datetime.utcnow()
        async with SessionLocal() as session:
            due = (await session.execute(
                select(UserWord).join(Word).where(
                    UserWord.user_id == user_id,
                    Word.category == category,
                    UserWord.next_review <= now
                )
            )).scalars().all()
            due = sorted(due, key=lambda x: (x.mastered, x.next_review))
            due_ids = {uw.word_id for uw in due}

            new_words = (await session.execute(
                select(Word).where(
                    Word.category == category,
                    ~Word.id.in_(due_ids) if due_ids else True
                )
            )).scalars().all()
            known_ids = set((await session.execute(
                select(UserWord.word_id).where(UserWord.user_id == user_id)
            )).scalars().all())
            new_words = [w for w in new_words if w.id not in known_ids]
            random.shuffle(new_words)
            selected_new = new_words[:new_count]

            items = [uw.word for uw in due[:max(new_count, 10)]] + selected_new
            if not items:
                all_words = (await session.execute(
                    select(Word).where(Word.category == category)
                )).scalars().all()
                random.shuffle(all_words)
                items = all_words[:new_count]

            lesson = Lesson(user_id=user_id, category=category)
            session.add(lesson)
            await session.commit()
            await session.refresh(lesson)
            return lesson.id, [w.id for w in items]

    @staticmethod
    async def get_word(word_id: int):
        async with SessionLocal() as session:
            return (await session.execute(select(Word).where(Word.id == word_id))).scalar_one()

    @staticmethod
    async def get_options(word_id: int):
        async with SessionLocal() as session:
            target = (await session.execute(select(Word).where(Word.id == word_id))).scalar_one()
            others = (await session.execute(
                select(Word).where(Word.id != word_id, Word.category == target.category)
            )).scalars().all()
            translations = list(dict.fromkeys(w.translation for w in others if w.translation != target.translation))
            options = [target.translation] + random.sample(translations, min(3, len(translations)))
            random.shuffle(options)
            return target, options

    @staticmethod
    async def record_answer(user_id, lesson_id, word_id, selected, correct, qtype="translation"):
        async with SessionLocal() as session:
            uw = (await session.execute(
                select(UserWord).where(UserWord.user_id == user_id, UserWord.word_id == word_id)
            )).scalar_one_or_none()
            if not uw:
                uw = UserWord(user_id=user_id, word_id=word_id, seen_count=0, correct_count=0,
                              wrong_count=0, streak=0, interval_days=1,
                              next_review=datetime.utcnow(), mastered=False)
                session.add(uw)

            uw.seen_count = (uw.seen_count or 0) + 1
            uw.correct_count = uw.correct_count or 0
            uw.wrong_count = uw.wrong_count or 0
            uw.streak = uw.streak or 0
            uw.interval_days = uw.interval_days or 1
            if correct:
                uw.correct_count += 1
                uw.streak += 1
                if uw.streak == 1: uw.interval_days = 1
                elif uw.streak == 2: uw.interval_days = 3
                elif uw.streak == 3: uw.interval_days = 7
                elif uw.streak == 4: uw.interval_days = 14
                else: uw.interval_days = min(60, uw.interval_days * 2)
                uw.next_review = datetime.utcnow() + timedelta(days=uw.interval_days)
                if uw.streak >= 5: uw.mastered = True
            else:
                uw.wrong_count += 1
                uw.streak = 0
                uw.interval_days = 1
                uw.next_review = datetime.utcnow() + timedelta(days=1)
                uw.mastered = False

            session.add(Answer(user_id=user_id, lesson_id=lesson_id, word_id=word_id,
                               question_type=qtype, selected=selected, correct=correct))
            lesson = await session.get(Lesson, lesson_id)
            lesson.total_questions = (lesson.total_questions or 0) + 1
            if correct: lesson.correct_answers = (lesson.correct_answers or 0) + 1
            else: lesson.wrong_answers = (lesson.wrong_answers or 0) + 1
            await session.commit()

    @staticmethod
    async def finish_lesson(lesson_id):
        async with SessionLocal() as session:
            lesson = await session.get(Lesson, lesson_id)
            if lesson:
                lesson.finished_at = datetime.utcnow()
                await session.commit()
                return lesson

    @staticmethod
    async def stats(user_id, category: str | None = None):
        async with SessionLocal() as session:
            conditions = [UserWord.user_id == user_id]
            if category:
                conditions.append(Word.category == category)
            studied = await session.scalar(select(func.count(UserWord.id)).join(Word).where(*conditions))
            correct = await session.scalar(select(func.sum(UserWord.correct_count)).join(Word).where(*conditions)) or 0
            wrong = await session.scalar(select(func.sum(UserWord.wrong_count)).join(Word).where(*conditions)) or 0
            total = correct + wrong
            difficult = (await session.execute(
                select(UserWord, Word).join(Word, Word.id == UserWord.word_id)
                .where(*conditions).order_by(UserWord.wrong_count.desc()).limit(5)
            )).all()
            return studied or 0, correct, wrong, total, difficult


class AdminService:
    @staticmethod
    async def overview():
        async with SessionLocal() as session:
            users = await session.scalar(select(func.count(User.id))) or 0
            active = await session.scalar(select(func.count(User.id)).where(User.is_active == True)) or 0
            words = await session.scalar(select(func.count(Word.id))) or 0
            lessons = await session.scalar(select(func.count(Lesson.id))) or 0
            answers = await session.scalar(select(func.count(Answer.id))) or 0
            return users, active, words, lessons, answers

    @staticmethod
    async def dictionary_stats():
        async with SessionLocal() as session:
            rows = (await session.execute(
                select(Word.category, func.count(Word.id)).group_by(Word.category)
            )).all()
            return dict(rows)

    @staticmethod
    async def all_active_user_ids():
        async with SessionLocal() as session:
            return list((await session.execute(
                select(User.telegram_id).where(User.is_active == True)
            )).scalars().all())

    @staticmethod
    async def add_word(infinitive, translation, example, category, past_simple="", past_participle=""):
        async with SessionLocal() as session:
            existing = (await session.execute(
                select(Word).where(Word.infinitive == infinitive)
            )).scalar_one_or_none()
            if existing:
                return False
            session.add(Word(infinitive=infinitive, past_simple=past_simple,
                             past_participle=past_participle, translation=translation,
                             example=example, category=category))
            await session.commit()
            return True
