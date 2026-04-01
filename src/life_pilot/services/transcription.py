"""Groq Whisper transcription service (replaces Deepgram)."""

import logging

import httpx

logger = logging.getLogger(__name__)

GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


class GroqTranscriber:
    """Service for transcribing audio using Groq Whisper API.

    Groq hosts OpenAI's Whisper large-v3 on LPU chips — free, fast (1-3 sec).
    Drop-in replacement for DeepgramTranscriber with same interface.
    """

    def __init__(self, api_key: str, language: str = "ru") -> None:
        self.api_key = api_key
        self.language = language

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe audio bytes to text via Groq Whisper API.

        Args:
            audio_bytes: Audio file content (ogg, mp3, wav, m4a, webm)

        Returns:
            Transcribed text

        Raises:
            Exception: If transcription fails
        """
        logger.info("Starting Groq transcription, audio size: %d bytes", len(audio_bytes))

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                GROQ_TRANSCRIPTION_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": ("audio.ogg", audio_bytes, "audio/ogg")},
                data={
                    "model": "whisper-large-v3-turbo",
                    "language": self.language,
                    "response_format": "text",
                },
            )

        if response.status_code != 200:
            error_msg = response.text[:300]
            logger.error("Groq transcription failed (%d): %s", response.status_code, error_msg)
            raise RuntimeError(f"Groq transcription failed: {error_msg}")

        transcript = response.text.strip()
        logger.info("Transcription complete: %d chars", len(transcript))
        return transcript


# Backward-compatible alias
DeepgramTranscriber = GroqTranscriber
