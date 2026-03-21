"""Smoke tests for Settings configuration."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from d_brain.config import Settings


def test_settings_loads_with_required_fields() -> None:
    """Settings should load when required fields are provided."""
    s = Settings(telegram_bot_token="tok", deepgram_api_key="dg")
    assert s.telegram_bot_token == "tok"
    assert s.deepgram_api_key == "dg"


def test_settings_missing_required_fields(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Settings should fail without required fields when no .env exists."""
    monkeypatch.chdir(tmp_path)  # no .env file here
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    with pytest.raises((ValidationError, Exception)):
        Settings()  # type: ignore[call-arg]


def test_google_token_path_expands_tilde() -> None:
    """google_token_path with ~ should be expanded to absolute path."""
    s = Settings(
        telegram_bot_token="tok",
        deepgram_api_key="dg",
        google_token_path="~/some/token.json",
    )
    assert not str(s.google_token_path).startswith("~")
    assert s.google_token_path.is_absolute()


def test_vault_path_expands_tilde(tmp_path: Path) -> None:
    """vault_path with ~ should be expanded to absolute path."""
    s = Settings(
        telegram_bot_token="tok",
        deepgram_api_key="dg",
        vault_path="~/my-vault",
    )
    assert not str(s.vault_path).startswith("~")
    assert s.vault_path.is_absolute()


def test_vault_path_relative_kept_as_is() -> None:
    """vault_path without ~ stays as given (relative paths allowed)."""
    s = Settings(
        telegram_bot_token="tok",
        deepgram_api_key="dg",
        vault_path="./vault",
    )
    assert str(s.vault_path) == "vault"


def test_allow_all_users_default_false() -> None:
    """allow_all_users should default to False for security."""
    s = Settings(telegram_bot_token="tok", deepgram_api_key="dg")
    assert s.allow_all_users is False


def test_allowed_user_ids_can_be_set() -> None:
    """allowed_user_ids can be set explicitly."""
    s = Settings(telegram_bot_token="tok", deepgram_api_key="dg", allowed_user_ids=[111, 222])
    assert s.allowed_user_ids == [111, 222]


def test_daily_path_derived_from_vault() -> None:
    """daily_path property should be vault_path / daily."""
    s = Settings(
        telegram_bot_token="tok",
        deepgram_api_key="dg",
        vault_path="/tmp/myvault",
    )
    assert s.daily_path == Path("/tmp/myvault/daily")
