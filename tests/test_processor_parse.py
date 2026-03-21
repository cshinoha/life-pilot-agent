"""Smoke tests for ClaudeProcessor.categorize_daily JSON parsing."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from d_brain.services.processor import ClaudeProcessor


@pytest.fixture
def processor(vault: Path) -> ClaudeProcessor:
    """ClaudeProcessor with mocked runner."""
    p = ClaudeProcessor(vault_path=vault, todoist_api_key="")
    p.runner = MagicMock()
    return p


def _make_daily(vault: Path, day: date, content: str) -> None:
    daily = vault / "daily" / f"{day.isoformat()}.md"
    daily.write_text(content, encoding="utf-8")


def test_categorize_missing_file(processor: ClaudeProcessor, vault: Path) -> None:
    """Should return error dict when daily file doesn't exist."""
    result = processor.categorize_daily(date(2099, 1, 1))
    assert "error" in result
    assert result.get("processed_entries") == 0


def test_categorize_valid_json(processor: ClaudeProcessor, vault: Path) -> None:
    """Should parse valid JSON response from Claude correctly."""
    _make_daily(vault, date(2025, 6, 15), "## 10:00 [text]\nBuy milk")
    processor.runner.run.return_value = {  # type: ignore[attr-defined]
        "report": '{"confident": [{"text": "Buy milk", "category": "task", "action": "buy"}], "uncertain": []}'
    }
    result = processor.categorize_daily(date(2025, 6, 15))
    assert "error" not in result
    assert "parse_error" not in result
    assert result["confident"] == [{"text": "Buy milk", "category": "task", "action": "buy"}]
    assert result["uncertain"] == []


def test_categorize_json_in_code_block(processor: ClaudeProcessor, vault: Path) -> None:
    """Should strip markdown code fences and parse JSON."""
    _make_daily(vault, date(2025, 6, 15), "## 10:00 [text]\nIdea")
    raw = '```json\n{"confident": [], "uncertain": []}\n```'
    processor.runner.run.return_value = {"report": raw}  # type: ignore[attr-defined]
    result = processor.categorize_daily(date(2025, 6, 15))
    assert "parse_error" not in result
    assert result["confident"] == []


def test_categorize_invalid_json_returns_parse_error(
    processor: ClaudeProcessor, vault: Path
) -> None:
    """Should return parse_error when Claude response is not valid JSON."""
    _make_daily(vault, date(2025, 6, 15), "## 10:00 [text]\nThought")
    processor.runner.run.return_value = {"report": "Sorry, I cannot process this."}  # type: ignore[attr-defined]
    result = processor.categorize_daily(date(2025, 6, 15))
    assert "parse_error" in result
    assert "raw" in result


def test_categorize_runner_error_passthrough(
    processor: ClaudeProcessor, vault: Path
) -> None:
    """Should pass through runner errors unchanged."""
    _make_daily(vault, date(2025, 6, 15), "## 10:00 [text]\nContent")
    processor.runner.run.return_value = {"error": "Claude unavailable"}  # type: ignore[attr-defined]
    result = processor.categorize_daily(date(2025, 6, 15))
    assert result == {"error": "Claude unavailable"}
