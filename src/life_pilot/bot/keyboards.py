"""Reply keyboards for Telegram bot."""

from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Main reply keyboard with common commands."""
    builder = ReplyKeyboardBuilder()
    # Row 1
    builder.button(text="🤖 Сделать")
    builder.button(text="🔍 Найти")
    builder.button(text="🤝 Коуч")
    # Row 2
    builder.button(text="⚡ Обработать")
    builder.button(text="📋 План")
    builder.button(text="📅 Неделя")
    # Row 3
    builder.button(text="📊 Статус")
    builder.button(text="ℹ️ Помощь")
    builder.button(text="🎲 Находка")
    # Row 4
    builder.button(text="🌅 Утро")
    builder.button(text="🌙 Вечер")
    builder.button(text="🧭 Обзор недели")
    # Row 5
    builder.button(text="🏥 Здоровье")
    builder.button(text="🧠 Память")
    builder.button(text="💬 Чат")
    builder.adjust(3, 3, 3, 3, 3)
    return builder.as_markup(resize_keyboard=True, is_persistent=True)
