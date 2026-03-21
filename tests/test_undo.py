"""Tests for undo system."""

from d_brain.bot.undo import UndoPayload, cleanup_expired, register_undo, _store
from datetime import datetime, timedelta


def test_register_undo_creates_entry() -> None:
    _store.clear()
    key = register_undo("abc123", "test action")
    assert key.startswith("undo_")
    assert key in _store
    assert _store[key].commit_sha == "abc123"


def test_payload_not_expired() -> None:
    p = UndoPayload(commit_sha="x", description="d")
    assert not p.expired


def test_payload_expired() -> None:
    p = UndoPayload(
        commit_sha="x",
        description="d",
        created_at=datetime.now() - timedelta(minutes=6),
    )
    assert p.expired


def test_cleanup_removes_expired() -> None:
    _store.clear()
    _store["old"] = UndoPayload(
        commit_sha="x", description="d",
        created_at=datetime.now() - timedelta(minutes=10),
    )
    _store["new"] = UndoPayload(commit_sha="y", description="d")
    removed = cleanup_expired()
    assert removed == 1
    assert "old" not in _store
    assert "new" in _store
