"""Voice message handler."""

import logging
from datetime import datetime
from html import escape as html_escape

from aiogram import Bot, Router
from aiogram.types import Message

from life_pilot.bot.utils import download_telegram_file
from life_pilot.config import get_settings
from life_pilot.services.dpv_routine import DpvRoutineService
from life_pilot.services.storage import VaultStorage
from life_pilot.services.transcription import GroqTranscriber

router = Router(name="voice")
logger = logging.getLogger(__name__)


@router.message(lambda m: m.voice is not None)
async def handle_voice(message: Message, bot: Bot) -> None:
    """Handle voice messages."""
    if not message.voice or not message.from_user:
        return

    await message.chat.do(action="typing")

    settings = get_settings()
    storage = VaultStorage(settings.vault_path)
    routine = DpvRoutineService(settings.vault_path)
    api_key = settings.groq_api_key or settings.deepgram_api_key
    transcriber = GroqTranscriber(api_key, settings.transcription_language)

    try:
        audio_bytes, _ = await download_telegram_file(bot, message.voice.file_id)
        transcript = await transcriber.transcribe(audio_bytes)

        if not transcript:
            await message.answer("Could not transcribe audio")
            return

        user_key = f"telegram:{message.from_user.id}"
        today = routine.today()
        weekly_result = routine.answer_weekly_review(
            user_key, today, transcript, "voice"
        )
        if weekly_result:
            await message.answer(weekly_result.message)
            return

        ritual_result = routine.answer_active_ritual(
            user_key, today, transcript, "voice"
        )
        if ritual_result:
            await message.answer(ritual_result.message)
            return

        timestamp = datetime.fromtimestamp(message.date.timestamp())
        storage.append_to_daily(transcript, timestamp, "[voice]")

        await message.answer(f"🎤 {html_escape(transcript)}\n\n✓ Сохранено")
        logger.info("Voice message saved: %d chars", len(transcript))

    except Exception as e:
        logger.exception("Error processing voice message")
        await message.answer(f"Error: {e}")
