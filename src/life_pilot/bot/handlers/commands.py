"""Command handlers for /start, /help, /status, /plan."""

import asyncio
import html
from datetime import date

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from life_pilot.bot.keyboards import get_main_keyboard
from life_pilot.config import get_settings
from life_pilot.services.factory import get_processor, get_runner
from life_pilot.services.storage import VaultStorage

router = Router(name="commands")


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Handle /start command."""
    await message.answer(
        "<b>Life Pilot</b> — твой голосовой дневник\n\n"
        "Отправляй мне:\n"
        "🎤 Голосовые сообщения\n"
        "💬 Текст\n"
        "📷 Фото\n"
        "↩️ Пересланные сообщения\n\n"
        "Всё будет сохранено и обработано.\n\n"
        "<b>Команды:</b>\n"
        "/do — выполнить произвольный запрос\n"
        "/recall — поиск по записям\n"
        "/process — обработать записи дня\n"
        "/plan — план на сегодня\n"
        "/weekly — недельный дайджест\n"
        "/monthly — месячный отчёт\n"
        "/status — статус сегодняшнего дня\n"
        "/health — здоровье vault\n"
        "/memory — статистика памяти\n"
        "/creative — случайные карточки\n"
        "/help — справка",
        reply_markup=get_main_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Handle /help command."""
    await message.answer(
        "⚡ <b>Обработать</b> — разобрать дневник: задачи, заметки, идеи\n"
        "🤖 <b>Сделать</b> — произвольная команда ИИ\n"
        "🔍 <b>Найти</b> — поиск по записям vault\n"
        "🤝 <b>Коуч</b> — диалог с коуч-ассистентом\n"
        "📋 <b>План</b> — текущие цели и задачи на день\n"
        "📅 <b>Неделя</b> — недельный дайджест\n"
        "📊 <b>Статус</b> — состояние бота и статистика\n"
        "🎲 <b>Находка</b> — случайная заметка\n"
        "🏥 <b>Здоровье</b> — метрики vault\n"
        "🧠 <b>Память</b> — долгосрочная память (MEMORY.md)\n"
        "❓ <b>Помощь</b> — эта справка"
    )


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    """Handle /status command."""
    settings = get_settings()
    storage = VaultStorage(settings.vault_path)
    runtime_status = get_runner().get_runtime_status(trigger_bootstrap=True)

    today = date.today()
    content = storage.read_daily(today)

    llm_block = (
        "\n\n🤖 <b>LLM:</b> "
        f"{html.escape(runtime_status['summary'])}"
    )
    if runtime_status["details"]:
        llm_block += f"\n{html.escape(runtime_status['details'])}"

    if not content:
        await message.answer(
            f"📅 <b>{today}</b>\n\nЗаписей пока нет.{llm_block}"
        )
        return

    lines = content.strip().split("\n")
    entries = [line for line in lines if line.startswith("## ")]

    voice_count = sum(1 for e in entries if "[voice]" in e)
    text_count = sum(1 for e in entries if "[text]" in e)
    photo_count = sum(1 for e in entries if "[photo]" in e)
    forward_count = sum(1 for e in entries if "[forward from:" in e)

    total = len(entries)

    await message.answer(
        f"📅 <b>{today}</b>\n\n"
        f"Всего записей: <b>{total}</b>\n"
        f"- 🎤 Голосовых: {voice_count}\n"
        f"- 💬 Текстовых: {text_count}\n"
        f"- 📷 Фото: {photo_count}\n"
        f"- ↩️ Пересланных: {forward_count}"
        f"{llm_block}"
    )

@router.message(Command("plan"))
async def cmd_plan(message: Message) -> None:
    """Handle /plan command - daily plan."""
    processor = get_processor()

    try:
        plan = await asyncio.to_thread(processor.get_daily_plan)
        await message.answer(plan, reply_markup=get_main_keyboard())
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
