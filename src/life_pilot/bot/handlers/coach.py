"""Coach Mode — conversational coaching dialogue with persistent context."""

from __future__ import annotations

import logging
import re
from html import escape as html_escape

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InaccessibleMessage,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from life_pilot.bot.progress import BusyError, run_with_progress
from life_pilot.bot.states import CoachStates
from life_pilot.bot.utils import send_formatted_report, transcribe_voice
from life_pilot.services.factory import get_processor

router = Router(name="coach")
logger = logging.getLogger(__name__)

_STOP_RE = re.compile(
    r"^(стоп|stop|завершить|закончить|выход|конец)[.!]?$", re.IGNORECASE
)

_WELCOME = (
    "🤝 <b>Coach Mode включён</b>\n\n"
    "Говори — я слушаю. Текст или голос.\n"
    "Напиши <i>«стоп»</i> чтобы завершить сессию."
)


def _zoom_keyboard() -> InlineKeyboardMarkup:
    """Return inline keyboard with Zoom Out / Zoom In buttons."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🔭 Zoom Out", callback_data="coach_zoom_out",
    )
    builder.button(
        text="🔬 Zoom In", callback_data="coach_zoom_in",
    )
    builder.adjust(2)
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


async def _start_coach(message: Message, state: FSMContext) -> None:
    """Shared entry: clear any previous state, start coach FSM."""
    await state.set_state(CoachStates.chatting)
    await state.set_data({"history": [], "turn": 0})
    await message.answer(_WELCOME, reply_markup=_zoom_keyboard())


@router.message(Command("coach"))
async def cmd_coach(message: Message, state: FSMContext) -> None:
    """Start coach mode via /coach command."""
    await _start_coach(message, state)


@router.message(F.text == "🤝 Коуч")
async def btn_coach(message: Message, state: FSMContext) -> None:
    """Start coach mode via keyboard button."""
    await _start_coach(message, state)


# ---------------------------------------------------------------------------
# Active dialogue
# ---------------------------------------------------------------------------


@router.message(CoachStates.chatting)
async def handle_coach_message(message: Message, bot: Bot, state: FSMContext) -> None:
    """Handle each message during coach session."""
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
        await _offer_save(message, state)
        return

    # --- Send to Claude ---
    data = await state.get_data()
    history: list[dict] = data.get("history", [])
    history.append({"role": "user", "content": user_text})

    status_msg = await message.answer("💭")
    processor = get_processor()
    try:
        result = await run_with_progress(
            processor.chat_with_coach, status_msg, "💭", history,
        )
    except BusyError as e:
        await status_msg.edit_text(str(e))
        history.pop()  # rollback
        await state.update_data(history=history)
        return

    # Store assistant reply in history (cap at 20 messages = 10 exchanges)
    assistant_text = result.get("report", "")
    history.append({"role": "assistant", "content": assistant_text})
    if len(history) > 20:
        history = history[-20:]

    turn = data.get("turn", 0) + 1
    await state.update_data(history=history, turn=turn)

    await send_formatted_report(status_msg, result)

    # Remind about stop every 5 turns
    if turn > 0 and turn % 5 == 0:
        await message.answer(
            "💡 <i>Напиши «стоп» чтобы завершить и сохранить сессию</i>"
        )


# ---------------------------------------------------------------------------
# End session
# ---------------------------------------------------------------------------


async def _offer_save(message: Message, state: FSMContext) -> None:
    """Ask user whether to save insights to coaching_context."""
    data = await state.get_data()
    history: list[dict] = data.get("history", [])

    await state.set_state(CoachStates.saving)

    if not history:
        await state.clear()
        await message.answer("Coach Mode выключен. Сессия была пустой.")
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="💾 Сохранить инсайты", callback_data="coach_save")
    builder.button(text="❌ Просто закрыть", callback_data="coach_close")
    builder.adjust(2)

    await message.answer(
        "Сессия завершена. Сохранить инсайты в профиль?",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data == "coach_save")
async def handle_coach_save(callback: CallbackQuery, state: FSMContext) -> None:
    """Summarize session and update coaching_context."""
    await callback.answer()

    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return

    await msg.edit_reply_markup(reply_markup=None)

    data = await state.get_data()
    history: list[dict] = data.get("history", [])
    await state.clear()

    status_msg = await msg.answer("⏳ Сохраняю инсайты...")
    processor = get_processor()
    try:
        result = await run_with_progress(
            processor.save_coach_insights, status_msg, "⏳ Сохраняю...", history,
        )
    except BusyError as e:
        await status_msg.edit_text(str(e))
        return

    await send_formatted_report(status_msg, result)


@router.callback_query(F.data == "coach_close")
async def handle_coach_close(callback: CallbackQuery, state: FSMContext) -> None:
    """Close session without saving."""
    await callback.answer()

    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return

    await msg.edit_reply_markup(reply_markup=None)
    await state.clear()
    await msg.answer("Coach Mode выключен.")


# ---------------------------------------------------------------------------
# Zoom callbacks
# ---------------------------------------------------------------------------


@router.callback_query(F.data == "coach_zoom_out")
async def handle_zoom_out(callback: CallbackQuery) -> None:
    """Zoom Out — big-picture perspective from coaching context."""
    await callback.answer("🔭 Zoom Out...")

    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return

    await msg.edit_reply_markup(reply_markup=None)
    status_msg = await msg.answer("🔭 Смотрю на большую картину...")
    processor = get_processor()
    try:
        report = await run_with_progress(
            processor.zoom_out,
            status_msg,
            "🔭 Смотрю на большую картину...",
        )
    except BusyError as e:
        await status_msg.edit_text(str(e))
        return
    await send_formatted_report(status_msg, report)


@router.callback_query(F.data == "coach_zoom_in")
async def handle_zoom_in(callback: CallbackQuery) -> None:
    """Zoom In — concrete actions for today."""
    await callback.answer("🔬 Zoom In...")

    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return

    await msg.edit_reply_markup(reply_markup=None)
    status_msg = await msg.answer("🎯 Собираю конкретные действия...")
    processor = get_processor()
    try:
        report = await run_with_progress(
            processor.zoom_in,
            status_msg,
            "🎯 Собираю конкретные действия...",
        )
    except BusyError as e:
        await status_msg.edit_text(str(e))
        return
    await send_formatted_report(status_msg, report)
