from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu(is_admin: bool = False):
    rows = [
        [InlineKeyboardButton(text="📚 Irregular Verbs", callback_data="topic:irregular_verbs")],
        [InlineKeyboardButton(text="🍎 Food Vocabulary", callback_data="topic:food")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats"),
         InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="👑 Админ-панель", callback_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_menu(current: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Новых слов: {current}", callback_data="noop")],
        [InlineKeyboardButton(text="5", callback_data="setwords:5"),
         InlineKeyboardButton(text="10", callback_data="setwords:10"),
         InlineKeyboardButton(text="15", callback_data="setwords:15"),
         InlineKeyboardButton(text="20", callback_data="setwords:20")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")],
    ])


def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика пользователей", callback_data="admin:stats")],
        [InlineKeyboardButton(text="📚 Статистика словаря", callback_data="admin:dictionary")],
        [InlineKeyboardButton(text="➕ Добавить слово", callback_data="admin:add_word")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="menu")],
    ])
