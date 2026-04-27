from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from life_pilot.services.dpv_routine import DpvRoutineService, strip_dpv_daily_block


def test_morning_routine_persists_state_and_daily_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    service = DpvRoutineService(tmp_path / "vault")
    user_id = "telegram:42"
    day = date(2026, 4, 25)

    started = service.start_ritual(user_id, day, "morning")
    assert "Оцени качество сна" in started.message

    answers = ["4", "3", "5", "семья", "сорваться с фокуса"]
    result = None
    for answer in answers:
        result = service.answer_active_ritual(user_id, day, answer, "text")

    assert result is not None
    assert result.completed is True
    assert "Утренний ритуал завершён" in result.message

    daily = (tmp_path / "vault" / "daily" / "2026-04-25.md").read_text(encoding="utf-8")
    assert "<!-- life-pilot:dpv:start -->" in daily
    assert "## DPV Daily Practice" in daily
    assert "- Sleep: 4" in daily
    assert "- семья" in daily
    assert "- сорваться с фокуса" in daily


def test_invalid_number_reasks_current_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    service = DpvRoutineService(tmp_path / "vault")
    user_id = "telegram:42"
    day = date(2026, 4, 25)

    service.start_ritual(user_id, day, "morning")
    result = service.answer_active_ritual(user_id, day, "десять", "text")

    assert result is not None
    assert result.completed is False
    assert "Пожалуйста, введи значение от 0 до 5" in result.message
    status = service.get_daily_status(user_id, day)
    assert "утренний: в процессе (шаг 1/5)" in status


def test_skip_advances_numeric_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    service = DpvRoutineService(tmp_path / "vault")
    user_id = "telegram:42"
    day = date(2026, 4, 25)

    service.start_ritual(user_id, day, "morning")
    result = service.skip_active_ritual(user_id, day)

    assert result is not None
    assert result.completed is False
    assert "Пропущено" in result.message
    assert "Оцени настроение сейчас" in result.message
    assert "утренний: в процессе (шаг 2/5)" in service.get_daily_status(user_id, day)

    daily = (tmp_path / "vault" / "daily" / "2026-04-25.md").read_text(encoding="utf-8")
    assert "- Sleep: —" in daily


def test_context_bridge_exposes_day_and_week_patterns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    service = DpvRoutineService(tmp_path / "vault")
    user_id = "telegram:42"
    day = date(2026, 4, 25)

    service.start_ritual(user_id, day, "morning")
    for answer in ["2", "2", "1", "семья", "сорваться с фокуса"]:
        service.answer_active_ritual(user_id, day, answer, "text")
    service.start_ritual(user_id, day, "evening")
    for answer in ["4", "ясность", "прогулка", "работа блоками", "отвлечения"]:
        service.answer_active_ritual(user_id, day, answer, "text")

    day_context = service.get_day_context(user_id, day)
    assert "DPV сегодня" in day_context
    assert "Сон: 2/5" in day_context
    assert "низкий ресурс" in day_context

    week_context = service.get_week_context(user_id, day)
    assert "DPV неделя" in week_context
    assert "Средний сон: 2.0/5" in week_context
    assert "Повторяющиеся страхи: сорваться с фокуса" in week_context

    daily = (tmp_path / "vault" / "daily" / "2026-04-25.md").read_text(encoding="utf-8")
    stripped = strip_dpv_daily_block(daily)
    assert "life-pilot:dpv:start" not in stripped
    assert "DPV Daily Practice" not in stripped


def test_weekly_review_summary_uses_completed_rituals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    service = DpvRoutineService(tmp_path / "vault")
    user_id = "telegram:42"
    day = date(2026, 4, 25)

    service.start_ritual(user_id, day, "morning")
    for answer in ["4", "3", "5", "семья", "сорваться с фокуса"]:
        service.answer_active_ritual(user_id, day, answer, "text")

    service.start_ritual(user_id, day, "evening")
    for answer in ["4", "ясность", "прогулка", "работа блоками", "меньше отвлекаться"]:
        service.answer_active_ritual(user_id, day, answer, "text")

    prompt = service.start_weekly_review(user_id, day)
    assert "Короткий обзор недели" in prompt.message

    result = service.answer_weekly_review(user_id, day, "короткий", "text")
    assert result is not None
    assert result.completed is True
    assert result.file_path is not None

    review = result.file_path.read_text(encoding="utf-8")
    assert "# Еженедельный DPV-обзор" in review
    assert "Средние метрики недели" in review
    assert "прогулка" in review
    assert "сорваться с фокуса" in review
