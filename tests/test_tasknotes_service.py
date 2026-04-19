"""Tests for the TaskNotes-backed task service."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from life_pilot.services.tasknotes import TaskNotesService


def make_service(tmp_path: Path) -> TaskNotesService:
    """Create a service rooted in a temporary vault."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    return TaskNotesService(vault_path)


def test_create_and_fetch_active_tasks(tmp_path: Path) -> None:
    """New task notes should be discoverable in runtime format."""
    service = make_service(tmp_path)

    created = service.create_task(
        "Позвонить клиенту",
        due="2026-04-20",
        priority="p2",
        projects=["clients"],
    )

    tasks = service.fetch_active_tasks()

    assert len(tasks) == 1
    assert tasks[0]["id"] == created["id"]
    assert tasks[0]["content"] == "Позвонить клиенту"
    assert tasks[0]["priority"] == 3
    assert tasks[0]["due"] == {"date": "2026-04-20"}


def test_close_task_updates_completed_count(tmp_path: Path) -> None:
    """Closing a task should remove it from active list and count it as completed."""
    service = make_service(tmp_path)
    created = service.create_task("Сделать обзор недели")

    success, error = service.close_task(created["id"])

    assert success is True
    assert error == ""
    assert service.fetch_active_tasks() == []
    assert service.fetch_completed_today(date.today().isoformat()) == 1


def test_update_and_reschedule_task(tmp_path: Path) -> None:
    """Task note updates should change title, heading, and due date."""
    service = make_service(tmp_path)
    created = service.create_task("Старая формулировка", due="2026-04-18")

    updated, update_error = service.update_content(created["id"], "Новая формулировка")
    moved, move_error = service.reschedule_to_today(created["id"])

    assert updated is True
    assert update_error == ""
    assert moved is True
    assert move_error == ""

    tasks = service.fetch_active_tasks()
    assert tasks[0]["content"] == "Новая формулировка"
    assert tasks[0]["due"] == {"date": date.today().isoformat()}

    task_file = next((tmp_path / "vault" / "TaskNotes" / "Tasks").glob("*.md"))
    task_text = task_file.read_text(encoding="utf-8")
    assert 'title: "Новая формулировка"' in task_text
    assert "# Новая формулировка" in task_text


def test_move_to_next_monday(tmp_path: Path) -> None:
    """Moving a task should assign the next Monday date."""
    service = make_service(tmp_path)
    created = service.create_task("Перенести задачу")

    success, error = service.move_to_next_monday(created["id"])

    next_monday = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 or 7)
    tasks = service.fetch_active_tasks()

    assert success is True
    assert error == ""
    assert tasks[0]["due"] == {"date": next_monday.isoformat()}
