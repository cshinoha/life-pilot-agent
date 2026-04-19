"""Tests for Telegram report formatting."""

from __future__ import annotations

import asyncio
from typing import Any

from life_pilot.bot.formatters import format_process_report, sanitize_telegram_html
from life_pilot.bot.handlers.process import _send_report_with_correction


def test_sanitize_telegram_html_strips_disallowed_tags() -> None:
    """Unsupported tags should be removed instead of shown to the user."""
    text = "<b>Итог</b><br><div>строка</div><span>ещё</span>"

    sanitized = sanitize_telegram_html(text)

    assert "<br>" not in sanitized
    assert "<div>" not in sanitized
    assert "<span>" not in sanitized
    assert "&lt;br&gt;" not in sanitized
    assert "&lt;div&gt;" not in sanitized
    assert "<b>Итог</b>" in sanitized
    assert "строка" in sanitized
    assert "ещё" in sanitized


def test_format_process_report_strips_extra_tags() -> None:
    """Formatted reports should stay Telegram-safe and readable."""
    report = {
        "report": "<b>Обработка</b><br><div>Готово</div>",
        "warnings": ["нестыковка < x"],
    }

    formatted = format_process_report(report)

    assert "<br>" not in formatted
    assert "&lt;br&gt;" not in formatted
    assert "<div>" not in formatted
    assert "&lt;div&gt;" not in formatted
    assert "⚠️ нестыковка &lt; x" in formatted


class _DummyMessage:
    def __init__(self) -> None:
        self.edits: list[tuple[str, Any]] = []
        self.answers: list[tuple[str, Any]] = []

    async def edit_text(self, text: str, parse_mode: Any = None) -> None:
        self.edits.append((text, parse_mode))

    async def answer(
        self, text: str, reply_markup: Any = None,
    ) -> _DummyMessage:
        self.answers.append((text, reply_markup))
        return self


class _DummyState:
    def __init__(self) -> None:
        self.data: dict[str, Any] = {}

    async def set_data(self, data: dict[str, Any]) -> None:
        self.data = data


def test_send_report_with_correction_strips_tags() -> None:
    """Correction flow should also sanitize model HTML before sending."""
    message = _DummyMessage()
    status = _DummyMessage()
    state = _DummyState()
    report = {"report": "<b>Скорректированный отчёт</b><br><div>Строка</div>"}

    asyncio.run(_send_report_with_correction(message, status, report, state))

    assert status.edits
    formatted = status.edits[0][0]
    assert "<br>" not in formatted
    assert "&lt;br&gt;" not in formatted
    assert "<div>" not in formatted
    assert "&lt;div&gt;" not in formatted
    assert "Скорректированный отчёт" in formatted
    assert state.data["last_report"] == formatted
    assert message.answers[0][0] == "Всё верно?"
