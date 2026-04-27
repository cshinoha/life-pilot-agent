"""Tests for ClaudeRunner runtime bootstrap behavior."""

from pathlib import Path

import pytest

from life_pilot.services.claude_runner import ClaudeRunner


def make_runner(tmp_path: Path, llm_cli: str = "codex") -> ClaudeRunner:
    """Create a runner rooted in a temporary project directory."""
    project_root = tmp_path / "project"
    vault_path = project_root / "vault"
    vault_path.mkdir(parents=True)
    return ClaudeRunner(vault_path=vault_path, llm_cli=llm_cli)


def test_run_returns_auth_message_without_invoking_exec(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Runner should stop early when Codex auth is still pending."""
    runner = make_runner(tmp_path)

    monkeypatch.setattr(
        runner,
        "get_runtime_status",
        lambda trigger_bootstrap=True: {
            "ready": False,
            "summary": "Codex ждёт авторизацию",
            "details": "Открой ссылку и введи код.",
        },
    )

    called = False

    def fake_execute(prompt: str, label: str, model: str = "") -> dict[str, str]:
        nonlocal called
        called = True
        return {"report": "OK"}

    monkeypatch.setattr(runner, "_execute", fake_execute)

    result = runner.run("prompt", "label")

    assert result["error"] == "Открой ссылку и введи код."
    assert result["processed_entries"] == 0
    assert called is False


def test_get_runtime_status_uses_pending_auth_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Existing pending device auth should be surfaced to the caller."""
    runner = make_runner(tmp_path)
    pending_auth = {
        "code": "ABCD-EFGH1",
        "login_url": "https://auth.openai.com/codex/device",
        "log_path": "/tmp/codex.log",
        "started_at": 1000.0,
        "expires_at": 2000.0,
        "pid": 12345,
    }

    monkeypatch.setattr(
        "life_pilot.services.claude_runner.shutil.which",
        lambda name: "/usr/bin/codex",
    )
    monkeypatch.setattr(runner, "_codex_is_logged_in", lambda: False)
    monkeypatch.setattr(runner, "_load_pending_codex_auth", lambda: pending_auth)

    status = runner.get_runtime_status(trigger_bootstrap=False)

    assert status["ready"] is False
    assert status["summary"] == "Codex ждёт авторизацию"
    details = status["details"]
    code = pending_auth["code"]
    assert isinstance(details, str)
    assert isinstance(code, str)
    assert code in details


def test_non_codex_runtime_is_ready(tmp_path: Path) -> None:
    """Claude mode should not require Codex auth checks."""
    runner = make_runner(tmp_path, llm_cli="claude")

    status = runner.get_runtime_status(trigger_bootstrap=True)

    assert status == {
        "ready": True,
        "summary": "claude готов",
        "details": "",
    }


def test_extract_device_auth_data_strips_ansi_sequences(tmp_path: Path) -> None:
    """ANSI-colored Codex output should still yield URL and device code."""
    runner = make_runner(tmp_path)
    auth_log = (
        "\x1b[94mhttps://auth.openai.com/codex/device\x1b[0m\n"
        "\x1b[94mP2KA-MDBPQ\x1b[0m\n"
    )

    login_url, code = runner._extract_device_auth_data(auth_log)

    assert login_url == "https://auth.openai.com/codex/device"
    assert code == "P2KA-MDBPQ"
