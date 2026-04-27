"""Undo system — track actions and allow reverting within TTL."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InaccessibleMessage,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from life_pilot.services.factory import get_git

logger = logging.getLogger(__name__)
router = Router(name="undo")

_UNDO_TTL = timedelta(minutes=5)


@dataclass
class UndoPayload:
    """Tracks what was done so it can be reverted."""

    commit_sha: str
    description: str
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def expired(self) -> bool:
        return datetime.now() - self.created_at > _UNDO_TTL


# In-memory store: callback_id -> payload
_store: dict[str, UndoPayload] = {}
_counter = 0


def register_undo(commit_sha: str, description: str) -> str:
    """Register an undo-able action.

    Args:
        commit_sha: Git commit SHA to revert.
        description: Human-readable description of what was done.

    Returns:
        Callback data string for the undo button.
    """
    global _counter
    _counter += 1
    key = f"undo_{_counter}"
    _store[key] = UndoPayload(commit_sha=commit_sha, description=description)
    return key


def build_undo_keyboard(
    callback_key: str,
    extra_buttons: list[tuple[str, str]] | None = None,
) -> InlineKeyboardMarkup:
    """Build keyboard with undo button and optional extra buttons.

    Args:
        callback_key: Undo callback data from register_undo().
        extra_buttons: Optional list of (text, callback_data) pairs.
    """
    builder = InlineKeyboardBuilder()
    if extra_buttons:
        for text, data in extra_buttons:
            builder.button(text=text, callback_data=data)
    builder.button(text="↩️ Отменить (5 мин)", callback_data=callback_key)
    # Extra buttons on first row, undo on its own row
    if extra_buttons:
        builder.adjust(len(extra_buttons), 1)
    else:
        builder.adjust(1)
    return builder.as_markup()


def cleanup_expired() -> int:
    """Remove expired undo payloads. Returns count removed."""
    expired_keys = [k for k, v in _store.items() if v.expired]
    for k in expired_keys:
        del _store[k]
    return len(expired_keys)


async def schedule_button_removal(
    message: "Message", delay_seconds: int = 300,
) -> None:
    """Remove undo keyboard after TTL expires."""
    await asyncio.sleep(delay_seconds)
    try:
        await message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass  # message may have been deleted or keyboard already removed


# ── Callback handler ─────────────────────────────────────────────────


@router.callback_query(F.data.startswith("undo_"))
async def handle_undo(callback: CallbackQuery) -> None:
    """Handle undo button press."""
    cleanup_expired()
    key = callback.data or ""
    payload = _store.pop(key, None)

    msg = callback.message
    if msg is None or isinstance(msg, InaccessibleMessage):
        return

    if payload is None:
        await callback.answer("⏰ Время отмены истекло", show_alert=True)
        await msg.edit_reply_markup(reply_markup=None)
        return

    if payload.expired:
        await callback.answer("⏰ Время отмены истекло", show_alert=True)
        await msg.edit_reply_markup(reply_markup=None)
        return

    await callback.answer("↩️ Отменяю...")

    git = get_git()
    ok, reason = await asyncio.to_thread(git.revert_commit, payload.commit_sha)

    if ok:
        await msg.edit_reply_markup(reply_markup=None)
        await msg.answer(
            f"↩️ <b>Отменено:</b> {payload.description}\n\n"
            "⚠️ Если были созданы task notes — удали их вручную."
        )
        logger.info("Undo successful: reverted %s", payload.commit_sha[:8])
    else:
        await msg.answer(
            f"❌ Не удалось отменить: {reason[:100]}\n"
            "Попробуй вручную: git revert в vault."
        )
        logger.error("Undo failed for %s: %s", payload.commit_sha[:8], reason)
