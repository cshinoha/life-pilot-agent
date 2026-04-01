"""Undo button utilities — schedule removal of stale inline buttons."""

from __future__ import annotations

import asyncio
import logging
import time

from aiogram.types import Message

logger = logging.getLogger(__name__)

# Pending removals: {message_id: (message, expire_ts)}
_pending: dict[int, tuple[Message, float]] = {}


async def schedule_button_removal(
    message: Message,
    delay_seconds: int = 300,
) -> None:
    """Schedule removal of inline keyboard from *message* after delay.

    Args:
        message: Telegram message with inline keyboard.
        delay_seconds: Seconds before the keyboard is removed (default 5 min).
    """
    expire_ts = time.monotonic() + delay_seconds
    _pending[message.message_id] = (message, expire_ts)

    await asyncio.sleep(delay_seconds)

    # Only remove if still pending (not already cleaned up)
    entry = _pending.pop(message.message_id, None)
    if entry is None:
        return

    try:
        await message.edit_reply_markup(reply_markup=None)
    except Exception:
        logger.debug(
            "Could not remove keyboard from message %s",
            message.message_id,
        )


async def cleanup_expired() -> None:
    """Remove keyboards from all expired pending messages.

    Call at the start of ``handle_undo()`` to clean up any buttons
    that survived past their expiry (e.g. if the sleep task was cancelled).
    """
    now = time.monotonic()
    expired_ids = [
        mid for mid, (_, ts) in _pending.items() if ts <= now
    ]
    for mid in expired_ids:
        entry = _pending.pop(mid, None)
        if entry is None:
            continue
        msg, _ = entry
        try:
            await msg.edit_reply_markup(reply_markup=None)
        except Exception:
            logger.debug(
                "cleanup_expired: could not remove keyboard from %s",
                mid,
            )
