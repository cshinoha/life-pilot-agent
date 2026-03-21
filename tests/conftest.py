"""Shared test fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """Create a minimal vault directory structure."""
    (tmp_path / "daily").mkdir()
    (tmp_path / "attachments").mkdir()
    return tmp_path
