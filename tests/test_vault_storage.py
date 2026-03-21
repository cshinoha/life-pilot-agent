"""Smoke tests for VaultStorage."""

from datetime import date, datetime
from pathlib import Path

import pytest

from d_brain.services.storage import VaultStorage


@pytest.fixture
def storage(vault: Path) -> VaultStorage:
    """VaultStorage instance backed by tmp vault."""
    return VaultStorage(vault)


def test_read_daily_nonexistent_returns_empty(storage: VaultStorage) -> None:
    """read_daily on a missing file should return empty string."""
    result = storage.read_daily(date(2099, 1, 1))
    assert result == ""


def test_append_creates_file(storage: VaultStorage) -> None:
    """append_to_daily should create the daily file if it doesn't exist."""
    ts = datetime(2025, 6, 15, 10, 30)
    storage.append_to_daily("Hello world", ts, "[text]")
    content = storage.read_daily(date(2025, 6, 15))
    assert "Hello world" in content


def test_append_does_not_overwrite(storage: VaultStorage) -> None:
    """Multiple appends should accumulate, not overwrite."""
    ts1 = datetime(2025, 6, 15, 10, 0)
    ts2 = datetime(2025, 6, 15, 11, 0)
    storage.append_to_daily("First entry", ts1, "[text]")
    storage.append_to_daily("Second entry", ts2, "[text]")
    content = storage.read_daily(date(2025, 6, 15))
    assert "First entry" in content
    assert "Second entry" in content


def test_append_includes_timestamp(storage: VaultStorage) -> None:
    """Appended entry should include time in HH:MM format."""
    ts = datetime(2025, 6, 15, 14, 45)
    storage.append_to_daily("Test", ts, "[voice]")
    content = storage.read_daily(date(2025, 6, 15))
    assert "14:45" in content


def test_get_daily_file_returns_correct_path(storage: VaultStorage, vault: Path) -> None:
    """get_daily_file should return path under vault/daily/."""
    path = storage.get_daily_file(date(2025, 6, 15))
    assert path == vault / "daily" / "2025-06-15.md"
