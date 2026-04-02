"""Weekly digest command handler."""

import asyncio
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InaccessibleMessage, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from life_pilot.bot.components.task_keyboard import create_task_keyboard
from life_pilot.bot.formatters import format_process_report
from life_pilot.bot.progress import BusyError, run_with_progress
from life_pilot.bot.states import WeeklyGoalsStates
from life_pilot.bot.utils import send_formatted_report
from life_pilot.config import get_settings
from life_pilot.services.factory import get_git, get_processor, get_todoist

router = Router(name="weekly")
logger = logging.getLogger(__name__)


def _check_weekly_goals_staleness(vault_path: Path) -> int | None:
    """Return days since goals/3-weekly.md was last modified, or None if not stale.

    Returns the number of days if stale (> 7 days old), otherwise None.
    """
    goals_path = vault_path / "goals" / "3-weekly.md"
    if not goals_path.exists():
        return None
    mtime = datetime.fromtimestamp(os.path.getmtime(goals_path))
    days_old = (datetime.now() - mtime).days
    return days_old if days_old > 7 else None


async def _send_stale_goals_prompt(bot: Bot, chat_id: int) -> None:
    """Send a staleness warning for weekly goals with an update button."""
    settings = get_settings()
    days_old = _check_weekly_goals_staleness(settings.vault_path)
    if days_old is None:
        return
    kb = InlineKeyboardBuilder()
    kb.button(text="📝 Обновить цели недели", callback_data="update_weekly_goals")
    await bot.send_message(
        chat_id,
        f"⚠️ Цели недели не обновлялись {days_old} дней. Хочешь обновить?",
        reply_markup=kb.as_markup(),
    )


@router.message(Command("weekly"))
async def cmd_weekly(message: Message) -> None:
    """Handle /weekly command - generate weekly digest."""
    user_id = message.from_user.id if message.from_user else "unknown"
    logger.info("Weekly digest triggered by user %s", user_id)

    status_msg = await message.answer("⏳ Генерирую недельный дайджест...")

    processor = get_processor()
    git = get_git()

    try:
        report = await run_with_progress(
            processor.generate_weekly, status_msg,
            "⏳ Генерирую дайджест...",
        )
    except BusyError as e:
        await status_msg.edit_text(str(e))
        return

    # Commit any changes (weekly goal updates, etc)
    if "error" not in report:
        ok, reason = await asyncio.to_thread(
            git.commit_and_push, "chore: weekly digest",
        )
        if not ok:
            report.setdefault("warnings", []).append(f"Vault not synced: {reason[:80]}")

    await send_formatted_report(status_msg, report)

    # ── Send per-task keyboards (ТЗ 1.1) ──────────────────────────────
    if "error" not in report:
        todoist = get_todoist()
        if todoist:
            try:
                tasks = await asyncio.to_thread(todoist.fetch_active_tasks)
            except Exception as e:
                logger.warning("Failed to fetch Todoist tasks for weekly: %s", e)
                tasks = []

            if tasks:
                # Filter: tasks due within the next 7 days or overdue
                today = date.today()
                cutoff = (today + timedelta(days=7)).isoformat()
                today_str = today.isoformat()

                relevant = [
                    t for t in tasks
                    if t.get("due") and t["due"].get("date", "") <= cutoff
                ]

                if relevant:
                    await message.answer(
                        f"📋 <b>Задачи к обзору ({len(relevant)}):</b>\n"
                        "Выбери действие для каждой задачи:"
                    )

                    for task in relevant:
                        task_id = str(task.get("id", ""))
                        content = task.get("content", "Без названия")
                        due_date = task.get("due", {}).get("date", "")
                        overdue = due_date < today_str if due_date else False

                        prefix = "⚠️ " if overdue else "📌 "
                        text = f"{prefix}{content}"
                        if due_date:
                            text += f"\n<i>Срок: {due_date}</i>"

                        await message.answer(
                            text,
                            reply_markup=create_task_keyboard(task_id, "weekly"),
                        )

    # ── Weekly goals staleness check ──────────────────────────────────
    if message.bot:
        chat_id = message.chat.id
        await _send_stale_goals_prompt(message.bot, chat_id)


# ── Scheduled job functions ───────────────────────────────────────────


async def scheduled_weekly_report(bot: Bot, chat_id: int) -> None:
    """Called by APScheduler on Saturday at 21:00.

    Skips on days 1-3 of the month — monthly GROW takes priority.
    """
    if date.today().day <= 3:
        logger.info("Weekly report: day 1-3 of month — deferring to monthly")
        return

    logger.info("Scheduled weekly report starting")
    processor = get_processor()
    git = get_git()

    try:
        report = await asyncio.to_thread(processor.generate_weekly)
    except Exception as e:
        logger.error("Scheduled weekly report failed: %s", e)
        try:
            await bot.send_message(chat_id, f"⚠️ Не удалось сгенерировать недельный дайджест: {e}")
        except Exception:
            pass
        return

    if "error" not in report:
        await asyncio.to_thread(git.commit_and_push, "chore: weekly digest")

    formatted = format_process_report(report)
    try:
        await bot.send_message(chat_id, formatted)
    except Exception:
        try:
            await bot.send_message(chat_id, formatted, parse_mode=None)
        except Exception:
            logger.exception("Failed to send scheduled weekly report")

    # ── Weekly goals staleness check ──────────────────────────────────
    await _send_stale_goals_prompt(bot, chat_id)


# ── Weekly goals update FSM ───────────────────────────────────────────


@router.callback_query(F.data == "update_weekly_goals")
async def handle_update_weekly_goals_prompt(
    callback: CallbackQuery, state: FSMContext
) -> None:
    """Start FSM to collect new weekly goals from the user."""
    await callback.answer()

    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return

    await msg.edit_reply_markup(reply_markup=None)
    await state.set_state(WeeklyGoalsStates.waiting_goals)
    await msg.answer(
        "Напиши свои цели на эту неделю (или отправь голосовое).\n\n"
        "Когда закончишь — отправь сообщение, и я сохраню его в <code>goals/3-weekly.md</code>."
    )


@router.message(WeeklyGoalsStates.waiting_goals)
async def handle_weekly_goals_input(message: Message, state: FSMContext) -> None:
    """Save user-provided weekly goals to vault."""
    text = message.text or message.caption or ""
    if not text:
        await message.answer("Пожалуйста, напиши текстом цели на неделю.")
        return

    settings = get_settings()
    goals_path = settings.vault_path / "goals" / "3-weekly.md"
    goals_path.parent.mkdir(parents=True, exist_ok=True)

    today = date.today()
    content = (
        f"# Цели на неделю\n\n"
        f"_Обновлено: {today.isoformat()}_\n\n"
        f"{text}\n"
    )

    try:
        await asyncio.to_thread(goals_path.write_text, content, "utf-8")
        await state.clear()
        await message.answer("✅ Цели на неделю сохранены в <code>goals/3-weekly.md</code>.")
        logger.info("Weekly goals updated by user on %s", today.isoformat())
    except Exception:
        logger.exception("Failed to save weekly goals")
        await state.clear()
        await message.answer("⚠️ Не удалось сохранить цели. Попробуй ещё раз.")
