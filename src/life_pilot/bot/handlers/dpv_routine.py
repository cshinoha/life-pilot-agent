"""DPV routine command handlers for the Life Pilot hybrid bot."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from life_pilot.config import get_settings
from life_pilot.services.dpv_routine import DpvRoutineService, RitualName

router = Router(name="dpv_routine")


def _service() -> DpvRoutineService:
    settings = get_settings()
    return DpvRoutineService(settings.vault_path)


def _user_key(message: Message) -> str:
    if message.from_user:
        return f"telegram:{message.from_user.id}"
    return f"telegram:{message.chat.id}"


async def _start_ritual(message: Message, ritual: RitualName) -> None:
    service = _service()
    result = service.start_ritual(_user_key(message), service.today(), ritual, "text")
    await message.answer(result.message)


@router.message(Command("morning"))
async def cmd_morning(message: Message) -> None:
    """Start the DPV morning ritual."""
    await _start_ritual(message, "morning")


@router.message(Command("evening"))
async def cmd_evening(message: Message) -> None:
    """Start the DPV evening ritual."""
    await _start_ritual(message, "evening")


@router.message(Command("resume"))
async def cmd_resume(message: Message) -> None:
    """Resume the active DPV ritual."""
    service = _service()
    result = service.resume_ritual(_user_key(message), service.today())
    await message.answer(
        result.message
        if result
        else "Сейчас нет активного ритуала. Используй /morning или /evening."
    )


@router.message(Command("skip"))
async def cmd_skip(message: Message) -> None:
    """Skip the current DPV ritual question."""
    service = _service()
    result = service.skip_active_ritual(_user_key(message), service.today())
    await message.answer(
        result.message
        if result
        else "Сейчас нет активного ритуала. Используй /morning или /evening."
    )


@router.message(Command("review_week"))
async def cmd_review_week(message: Message) -> None:
    """Start the DPV weekly summary/deep reflection flow."""
    service = _service()
    result = service.start_weekly_review(_user_key(message), service.today(), "text")
    await message.answer(result.message)


@router.message(F.text == "🌅 Утро")
async def btn_morning(message: Message) -> None:
    """Start morning ritual from reply keyboard."""
    await cmd_morning(message)


@router.message(F.text == "🌙 Вечер")
async def btn_evening(message: Message) -> None:
    """Start evening ritual from reply keyboard."""
    await cmd_evening(message)


@router.message(F.text == "🧭 Обзор недели")
async def btn_review_week(message: Message) -> None:
    """Start DPV weekly review from reply keyboard."""
    await cmd_review_week(message)
