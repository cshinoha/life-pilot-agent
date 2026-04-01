"""Free chat with Claude — conversational mode without coaching frame."""

from __future__ import annotations

import logging
import re
from html import escape as html_escape

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from d_brain.bot.progress import BusyError, run_with_progress
from d_brain.bot.states import ChatStates
from d_brain.bot.utils import send_formatted_report, transcribe_voice
from d_brain.services.factory import get_processor

router = Router(name="chat")
logger = logging.getLogger(__name__)

_STOP_RE = re.compile(
    r"^(стоп|stop|завершить|закончить|выход|конец)[.!]?$",
    re.IGNORECASE,
)

_WELCOME = (
    "💬 <b>Свободный чат включён</b>\n\n"
    "Пиши что угодно — текст или голос.\n"
    "Напиши <i>«стоп»</i> чтобы выйти."
)

_EXIT_MSG = "💬 Чат завершён."

# Auto-exit reminder interval (minutes)
_REMINDER_MINUTES = 15


# ---------------------------------------------------------------------------
# Entry point (shared between /chat command and button)
# ---------------------------------------------------------------------------


async def start_chat(message: Message, state: FSMContext) -> None:
    """Start free chat session — public helper for buttons.py."""
    await state.set_state(ChatStates.chatting)
    await state.set_data({
        "history": [],
        "turn": 0,
    })
    await message.answer(_WELCOME)


@router.message(Command("chat"))
async def cmd_chat(message: Message, state: FSMContext) -> None:
    """Start free chat via /chat command."""
    await start_chat(message, state)


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
        await message.answer(
            "Отправь текст или голосовое сообщение.",
        )
        return

    # --- Stop trigger ---
    if _STOP_RE.match(user_text.strip()):
        await state.clear()
        await message.answer(_EXIT_MSG)
        return

    # --- Build history and send to Claude ---
    data = await state.get_data()
    history: list[dict[str, str]] = data.get("history", [])
    history.append({"role": "user", "content": user_text})

    # Build a combined prompt from history for execute_prompt
    history_block = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: "
        f"{m['content']}"
        for m in history[:-1]
    )
    last_msg = history[-1]["content"]

    prompt = (
        "Ты ведёшь свободный чат с пользователем. "
        "Отвечай дружелюбно и по делу.\n\n"
    )
    if history_block:
        prompt += f"ИСТОРИЯ:\n{history_block}\n\n"
    prompt += f"СООБЩЕНИЕ:\n{last_msg}"

    status_msg = await message.answer("💭")
    processor = get_processor()
    try:
        result = await run_with_progress(
            processor.execute_prompt,
            status_msg,
            "💭",
            prompt,
        )
    except BusyError as e:
        await status_msg.edit_text(str(e))
        history.pop()  # rollback
        await state.update_data(history=history)
        return

    # Store assistant reply (cap at 20 messages = 10 exchanges)
    assistant_text = result.get("report", "")
    history.append({"role": "assistant", "content": assistant_text})
    if len(history) > 20:
        history = history[-20:]

    turn = data.get("turn", 0) + 1
    await state.update_data(history=history, turn=turn)

    await send_formatted_report(status_msg, result)

    # Auto-exit reminder every _REMINDER_MINUTES turns worth of time
    # Approximate: remind every 15 min worth of exchanges (~5 turns)
    reminder_interval = max(1, _REMINDER_MINUTES // 3)
    if turn > 0 and turn % reminder_interval == 0:
        await message.answer(
            "💡 <i>Напиши «стоп» чтобы завершить чат</i>",
        )
