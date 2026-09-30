import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.config import settings
from app.db import init_db, SessionLocal
from app.seed import seed_words
from app.services import LearningService, AdminService
from app.keyboards import main_menu, settings_menu, admin_menu
from app.models import User
from sqlalchemy import select


dp = Dispatcher()
BOT: Bot | None = None
sessions = {}
admin_states = {}

CATEGORY_NAMES = {
    "irregular_verbs": "📚 Irregular Verbs",
    "food": "🍎 Food Vocabulary",
}


def is_admin(tg_user) -> bool:
    configured_username = (settings.admin_username or "").strip().lstrip("@").lower()
    username_ok = bool(configured_username and (tg_user.username or "").lower() == configured_username)
    id_ok = settings.admin_user_id > 0 and tg_user.id == settings.admin_user_id
    return username_ok or id_ok


async def get_user(tg_user):
    return await LearningService.get_or_create_user(tg_user.id, tg_user.username)


async def start_lesson(tg_user, chat_id, category="irregular_verbs"):
    user = await get_user(tg_user)
    lesson_id, word_ids = await LearningService.create_lesson(user.id, user.daily_new_words, category)
    if not word_ids:
        await BOT.send_message(chat_id, f"Пока нет слов в теме {CATEGORY_NAMES[category]}.", reply_markup=main_menu(is_admin(tg_user)))
        return
    sessions[tg_user.id] = {
        "lesson_id": lesson_id, "queue": word_ids, "index": 0,
        "mistakes": [], "current": None, "phase": "main", "category": category,
        "options": [], "is_admin": is_admin(tg_user),
    }
    await send_question(tg_user.id, chat_id)


async def send_question(user_id, chat_id):
    state = sessions.get(user_id)
    if not state:
        return
    if state["index"] >= len(state["queue"]):
        if state["phase"] == "main" and state["mistakes"]:
            state["phase"] = "mistakes"
            state["queue"] = list(dict.fromkeys(state["mistakes"]))
            state["index"] = 0
            state["mistakes"] = []
            await BOT.send_message(chat_id, "🔁 Теперь повторим ошибки.")
        else:
            lesson = await LearningService.finish_lesson(state["lesson_id"])
            sessions.pop(user_id, None)
            if lesson:
                accuracy = round(lesson.correct_answers / lesson.total_questions * 100) if lesson.total_questions else 0
                await BOT.send_message(
                    chat_id,
                    f"🎉 Урок завершён!\n\n{CATEGORY_NAMES[state['category']]}\n"
                    f"Вопросов: {lesson.total_questions}\nПравильно: {lesson.correct_answers}\n"
                    f"Ошибок: {lesson.wrong_answers}\nТочность: {accuracy}%\n\n⭐ Продолжай в том же духе!",
                    reply_markup=main_menu(state["is_admin"]),
                )
            return

    word_id = state["queue"][state["index"]]
    state["current"] = word_id
    word, options = await LearningService.get_options(word_id)
    builder = InlineKeyboardBuilder()
    state["options"] = options
    for index, option in enumerate(options):
        builder.button(text=option, callback_data=f"answer:{word_id}:{index}")
    builder.adjust(1)
    position = state["index"] + 1
    total = len(state["queue"])
    if state["category"] == "irregular_verbs":
        text = (f"📚 {CATEGORY_NAMES[state['category']]}\nВопрос {position}/{total}\n\n"
                f"**{word.infinitive.upper()}**\n{word.past_simple} — {word.past_participle}\n\nВыбери перевод:")
    else:
        text = (f"🍎 {CATEGORY_NAMES[state['category']]}\nВопрос {position}/{total}\n\n"
                f"**{word.infinitive.upper()}**\n\nВыбери перевод:")
    await BOT.send_message(chat_id, text, reply_markup=builder.as_markup(), parse_mode="Markdown")


@dp.message(CommandStart())
async def cmd_start(message: Message):
    user = await get_user(message.from_user)
    await message.answer(
        "🇬🇧 **English Trainer**\n\n"
        "Выбирай тему и учи слова через короткие квизы.\n\n"
        "📚 Неправильные глаголы — все 3 формы\n"
        "🍎 Food Vocabulary — обычная лексика по теме еды\n"
        "🔁 Ошибки повторяются в конце урока\n"
        "🧠 Сложные слова автоматически возвращаются позже\n\n"
        f"📚 Новых слов в день: {user.daily_new_words}",
        reply_markup=main_menu(is_admin(message.from_user)), parse_mode="Markdown"
    )


@dp.message(Command("lesson"))
async def cmd_lesson(message: Message):
    await start_lesson(message.from_user, message.chat.id)


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    user = await get_user(message.from_user)
    await show_stats(message, user.id, message.from_user)


@dp.message(Command("settings"))
async def cmd_settings(message: Message):
    user = await get_user(message.from_user)
    await message.answer("⚙️ Настройки", reply_markup=settings_menu(user.daily_new_words))


@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user):
        await message.answer("Нет доступа.")
        return
    await message.answer("👑 Админ-панель", reply_markup=admin_menu())


@dp.message(Command("cancel"))
async def cmd_cancel(message: Message):
    admin_states.pop(message.from_user.id, None)
    await message.answer("Отменено.", reply_markup=main_menu(is_admin(message.from_user)))


@dp.callback_query(F.data == "menu")
async def cb_menu(call: CallbackQuery):
    await call.answer()
    await call.message.edit_text("Главное меню:", reply_markup=main_menu(is_admin(call.from_user)))


@dp.callback_query(F.data.startswith("topic:"))
async def cb_topic(call: CallbackQuery):
    await call.answer()
    category = call.data.split(":", 1)[1]
    await call.message.answer(f"📚 Начинаем {CATEGORY_NAMES.get(category, category)}...")
    await start_lesson(call.from_user, call.message.chat.id, category)


@dp.callback_query(F.data == "stats")
async def cb_stats(call: CallbackQuery):
    await call.answer()
    user = await get_user(call.from_user)
    await show_stats(call.message, user.id, call.from_user)


async def show_stats(message, user_id, tg_user=None):
    lines = ["📊 **Твоя статистика**", ""]
    for category in ("irregular_verbs", "food"):
        studied, correct, wrong, total, difficult = await LearningService.stats(user_id, category)
        accuracy = round(correct / total * 100) if total else 0
        lines += [
            f"**{CATEGORY_NAMES[category]}**",
            f"Изучено слов: **{studied}**",
            f"Ответов: **{total}** · Правильно: **{correct}** · Ошибок: **{wrong}**",
            f"Точность: **{accuracy}%**",
            "",
        ]
        if difficult:
            lines.append("🔴 Сложные слова: " + ", ".join(f"{w.infinitive} ({uw.wrong_count})" for uw, w in difficult[:3]))
            lines.append("")
    await message.answer("\n".join(lines), parse_mode="Markdown", reply_markup=main_menu(is_admin(tg_user) if tg_user else False))


@dp.callback_query(F.data == "settings")
async def cb_settings(call: CallbackQuery):
    await call.answer()
    user = await get_user(call.from_user)
    await call.message.edit_text("⚙️ Сколько новых слов добавлять в ежедневный урок?", reply_markup=settings_menu(user.daily_new_words))


@dp.callback_query(F.data.startswith("setwords:"))
async def cb_setwords(call: CallbackQuery):
    value = int(call.data.split(":")[1])
    async with SessionLocal() as session:
        user = (await session.execute(select(User).where(User.telegram_id == call.from_user.id))).scalar_one()
        user.daily_new_words = value
        await session.commit()
    await call.answer(f"Установлено: {value}")
    await call.message.edit_text(f"✅ Новых слов в день: {value}", reply_markup=main_menu(is_admin(call.from_user)))


@dp.callback_query(F.data == "noop")
async def cb_noop(call: CallbackQuery):
    await call.answer()


@dp.callback_query(F.data.startswith("answer:"))
async def cb_answer(call: CallbackQuery):
    state = sessions.get(call.from_user.id)
    if not state:
        await call.answer("Урок уже завершён. Запусти новый.", show_alert=True)
        return
    _, word_id_s, option_index_s = call.data.split(":", 2)
    word_id = int(word_id_s)
    option_index = int(option_index_s)
    options = state.get("options", [])
    if option_index < 0 or option_index >= len(options):
        await call.answer("Вариант ответа устарел. Запусти урок заново.", show_alert=True)
        return
    selected = options[option_index]
    if state["current"] != word_id:
        await call.answer("Этот вопрос уже обработан.", show_alert=True)
        return
    word = await LearningService.get_word(word_id)
    correct = selected == word.translation
    await LearningService.record_answer((await get_user(call.from_user)).id, state["lesson_id"], word_id, selected, correct)
    if not correct and state["phase"] == "main":
        state["mistakes"].append(word_id)
    state["index"] += 1
    state["current"] = None
    forms = f"**{word.infinitive} — {word.past_simple} — {word.past_participle}**\n" if state["category"] == "irregular_verbs" else f"**{word.infinitive}**\n"
    if correct:
        text = f"✅ **Верно!**\n\n{forms}🇷🇺 {word.translation}\n\n💬 {word.example}"
    else:
        text = f"❌ **Неверно**\n\nПравильный ответ: **{word.translation}**\n\n{forms}💬 {word.example}\n\n🔁 Я повторю это слово в конце урока."
    await call.answer("Правильно!" if correct else "Неверно")
    await call.message.edit_text(text, parse_mode="Markdown")
    await asyncio.sleep(0.7)
    await send_question(call.from_user.id, call.message.chat.id)


@dp.callback_query(F.data == "admin")
async def cb_admin(call: CallbackQuery):
    await call.answer()
    if not is_admin(call.from_user):
        await call.message.answer("Нет доступа.")
        return
    await call.message.edit_text("👑 **Админ-панель**", reply_markup=admin_menu(), parse_mode="Markdown")


@dp.callback_query(F.data == "admin:stats")
async def cb_admin_stats(call: CallbackQuery):
    await call.answer()
    if not is_admin(call.from_user): return
    users, active, words, lessons, answers = await AdminService.overview()
    await call.message.answer(f"📊 **Пользователи**\n\nВсего: **{users}**\nАктивных: **{active}**\n\n📚 Слов: **{words}**\nУроков: **{lessons}**\nОтветов: **{answers}**", parse_mode="Markdown", reply_markup=admin_menu())


@dp.callback_query(F.data == "admin:dictionary")
async def cb_admin_dictionary(call: CallbackQuery):
    await call.answer()
    if not is_admin(call.from_user): return
    stats = await AdminService.dictionary_stats()
    text = "📚 **Словарь**\n\n" + "\n".join(f"{CATEGORY_NAMES.get(k, k)}: **{v}**" for k, v in stats.items())
    await call.message.answer(text, parse_mode="Markdown", reply_markup=admin_menu())


@dp.callback_query(F.data == "admin:add_word")
async def cb_admin_add_word(call: CallbackQuery):
    await call.answer()
    if not is_admin(call.from_user): return
    admin_states[call.from_user.id] = "add_word"
    await call.message.answer(
        "➕ Отправь слово одной строкой:\n\n"
        "Для Food:\n`food | apple | яблоко | I eat an apple.`\n\n"
        "Для глагола:\n`irregular_verbs | go | идти | I go home. | went | gone`\n\n"
        "После этого слово сразу появится в словаре. /cancel — отмена.", parse_mode="Markdown"
    )


@dp.callback_query(F.data == "admin:broadcast")
async def cb_admin_broadcast(call: CallbackQuery):
    await call.answer()
    if not is_admin(call.from_user): return
    admin_states[call.from_user.id] = "broadcast"
    await call.message.answer("📢 Отправь текст рассылки одним сообщением. /cancel — отмена.")


@dp.message(F.text)
async def admin_text_handler(message: Message):
    state = admin_states.get(message.from_user.id)
    if not state or not is_admin(message.from_user):
        return
    admin_states.pop(message.from_user.id, None)
    if state == "broadcast":
        user_ids = await AdminService.all_active_user_ids()
        sent = 0
        failed = 0
        for user_id in user_ids:
            try:
                await BOT.send_message(user_id, message.text)
                sent += 1
            except Exception:
                failed += 1
        await message.answer(f"📢 Рассылка завершена.\nОтправлено: {sent}\nОшибок: {failed}", reply_markup=admin_menu())
        return
    if state == "add_word":
        try:
            parts = [p.strip() for p in message.text.split("|")]
            if len(parts) not in (4, 6):
                raise ValueError
            category, english, translation, example = parts[:4]
            if category not in CATEGORY_NAMES:
                raise ValueError
            past_simple = parts[4] if len(parts) == 6 else ""
            past_participle = parts[5] if len(parts) == 6 else ""
            ok = await AdminService.add_word(english, translation, example, category, past_simple, past_participle)
            if ok:
                await message.answer(f"✅ Добавлено: **{english}** — {translation}", parse_mode="Markdown", reply_markup=admin_menu())
            else:
                await message.answer("⚠️ Такое английское слово уже есть в словаре.", reply_markup=admin_menu())
        except ValueError:
            await message.answer("❌ Неверный формат. Используй `/cancel` и попробуй ещё раз.", parse_mode="Markdown", reply_markup=admin_menu())


async def user_is_admin_by_db(user_id: int) -> bool:
    async with SessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            return False
        configured_username = (settings.admin_username or "").strip().lstrip("@").lower()
        return (settings.admin_user_id > 0 and user.telegram_id == settings.admin_user_id) or (bool(configured_username) and (user.username or "").lower() == configured_username)


async def daily_lessons(bot: Bot):
    async with SessionLocal() as session:
        users = (await session.execute(select(User).where(User.is_active == True))).scalars().all()
    for user in users:
        try:
            admin = await user_is_admin_by_db(user.id)
            await bot.send_message(user.telegram_id, "🌅 **Доброе утро!**\n\n📚 Выбери тему для сегодняшнего урока.", parse_mode="Markdown", reply_markup=main_menu(admin))
        except Exception:
            pass


async def main():
    await init_db()
    await seed_words()
    global BOT
    BOT = Bot(settings.bot_token)
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    scheduler.add_job(daily_lessons, CronTrigger(hour=settings.lesson_hour, minute=settings.lesson_minute), args=[BOT], id="daily_lessons", replace_existing=True)
    scheduler.start()
    print("Bot started")
    await dp.start_polling(BOT)


if __name__ == "__main__":
    asyncio.run(main())
