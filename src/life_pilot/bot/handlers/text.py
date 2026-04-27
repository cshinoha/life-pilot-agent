"""Text message handler."""

import logging
from datetime import datetime

from aiogram import Router
from aiogram.types import Message

from life_pilot.config import get_settings
from life_pilot.services.dpv_routine import DpvRoutineService
from life_pilot.services.storage import VaultStorage

router = Router(name="text")
logger = logging.getLogger(__name__)


@router.message(lambda m: m.text is not None and not m.text.startswith("/"))
async def handle_text(message: Message) -> None:
    """Handle text messages (excluding commands)."""
    if not message.text or not message.from_user:
        return

    text = message.text

    settings = get_settings()
    storage = VaultStorage(settings.vault_path)
    routine = DpvRoutineService(settings.vault_path)
    user_key = f"telegram:{message.from_user.id}"
    today = routine.today()

    weekly_result = routine.answer_weekly_review(user_key, today, text, "text")
    if weekly_result:
        await message.answer(weekly_result.message)
        return

    ritual_result = routine.answer_active_ritual(user_key, today, text, "text")
    if ritual_result:
        await message.answer(ritual_result.message)
        return

    timestamp = datetime.fromtimestamp(message.date.timestamp())
    storage.append_to_daily(text, timestamp, "[text]")

    await message.answer("✓ Сохранено")
    logger.info("Text message saved: %d chars", len(text))
