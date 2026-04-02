"""Free Chat — open-ended dialogue with Claude, no coaching frame."""

from __future__ import annotations

import asyncio
import logging
import re
from html import escape as html_escape

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from life_pilot.bot.keyboards import get_main_keyboard
from life_pilot.bot.progress import BusyError, run_with_progress
from life_pilot.bot.states import ChatStates
from life_pilot.bot.utils import send_formatted_report, transcribe_voice
from life_pilot.services.factory import get_processor

router = Router(name="chat")
logger = logging.getLogger(__name__)

_STOP_RE = re.compile(
    r"^(стоп|stop|выход|exit|хватит)[.!?]?$",
    re.IGNORECASE,
)

_WELCOME = (
    "💬 <b>Свободный чат включён</b>\n\n"
    "Пиши что угодно — текст или голос.\n"
    "Напиши <i>«стоп»</i> чтобы выйти."
)

_TIMEOUT_SECONDS = 15 * 60  # 15 minutes


# ---------------------------------------------------------------------------
# Timeout watchdog
# ---------------------------------------------------------------------------

_timeout_tasks: dict[int, asyncio.Task[None]] = {}


async def _timeout_watchdog(chat_id: int, state: FSMContext, bot: Bot) -> None:
    """Auto-exit chat after inactivity."""
    await asyncio.sleep(_TIMEOUT_SECONDS)
    current = await state.get_state()
    if current == ChatStates.chatting.state:
        await state.clear()
        await bot.send_message(
            chat_id,
            "💬 Чат выключен (15 мин тишины).",
            reply_markup=get_main_keyboard(),
        )


def _reset_timeout(chat_id: int, state: FSMContext, bot: Bot) -> None:
    """Cancel old timeout and start a new one."""
    old = _timeout_tasks.pop(chat_id, None)
    if old and not old.done():
        old.cancel()
    _timeout_tasks[chat_id] = asyncio.create_task(
        _timeout_watchdog(chat_id, state, bot),
    )


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


async def _start_chat(message: Message, state: FSMContext, bot: Bot) -> None:
    """Start free chat session."""
    await state.set_state(ChatStates.chatting)
    await state.set_data({"history": [], "turn": 0})
    await message.answer(_WELCOME)
    _reset_timeout(message.chat.id, state, bot)


@router.message(Command("chat"))
async def cmd_chat(message: Message, state: FSMContext, bot: Bot) -> None:
    """Start free chat via /chat command."""
    await _start_chat(message, state, bot)


@router.message(F.text == "💬 Чат")
async def btn_chat(message: Message, state: FSMContext, bot: Bot) -> None:
    """Start free chat via keyboard button."""
    await _start_chat(message, state, bot)


# ---------------------------------------------------------------------------
# Active dialogue
# ---------------------------------------------------------------------------


@router.message(ChatStates.chatting)
async def handle_chat_message(
    message: Message, bot: Bot, state: FSMContext,
) -> None:
    """Handle each message during free chat session."""
    if not message.from_user:
        return

    # --- Resolve text (text or voice) ---
    user_text: str | None = None

    if message.text:
        user_text = message.text
    elif message.voice:
        await message.chat.do(action="typing")
        user_text = await transcribe_voice(bot, message)
        if not user_text:
            return
        await message.answer(f"🎤 <i>{html_escape(user_text)}</i>")
    else:
        await message.answer("Отправь текст или голосовое сообщение.")
        return

    # --- Stop trigger ---
    if _STOP_RE.match(user_text.strip()):
        await _stop_chat(message, state)
        return

    _reset_timeout(message.chat.id, state, bot)

    data = await state.get_data()
    history: list[dict[str, str]] = data.get("history", [])
    history.append({"role": "user", "content": user_text})

    status_msg = await message.answer("💭")
    processor = get_processor()
    try:
        result = await run_with_progress(
            processor.chat_free, status_msg, "💭", history,
        )
    except BusyError as e:
        await status_msg.edit_text(str(e))
        history.pop()
        await state.update_data(history=history)
        return

    assistant_text = result.get("report", "")
    history.append({"role": "assistant", "content": assistant_text})
    if len(history) > 30:
        history = history[-30:]

    turn = data.get("turn", 0) + 1
    await state.update_data(history=history, turn=turn)

    await send_formatted_report(status_msg, result)


# ---------------------------------------------------------------------------
# End session
# ---------------------------------------------------------------------------


async def _stop_chat(message: Message, state: FSMContext) -> None:
    """Exit free chat mode."""
    old = _timeout_tasks.pop(message.chat.id, None)
    if old and not old.done():
        old.cancel()
    await state.clear()
    await message.answer(
        "💬 Чат выключен.",
        reply_markup=get_main_keyboard(),
    )
