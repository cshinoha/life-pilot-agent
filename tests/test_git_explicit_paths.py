"""Tests for git.py explicit paths (no git add -A)."""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from d_brain.services.git import VaultGit


@pytest.fixture
def git(tmp_path: Path) -> VaultGit:
    return VaultGit(tmp_path)


def test_commit_changes_uses_explicit_paths(git: VaultGit) -> None:
    """commit_changes should add specific vault dirs, not -A."""
    with patch.object(git, "_run_git") as mock:
        mock.return_value = MagicMock(returncode=0, stdout="M daily/x.md\n")
        git.commit_changes("test")

        add_call = mock.call_args_list[1]  # [0]=status, [1]=add
        args = add_call[0]
        assert args[0] == "add"
        assert "-A" not in args
        assert "daily/" in args
        assert "goals/" in args


def test_commit_changes_does_not_add_env(git: VaultGit) -> None:
    """commit_changes should never stage .env files."""
    with patch.object(git, "_run_git") as mock:
        mock.return_value = MagicMock(returncode=0, stdout="M .env\n")
        git.commit_changes("test")

        add_call = mock.call_args_list[1]
        args = add_call[0]
        assert ".env" not in args


def test_revert_commit(git: VaultGit) -> None:
    """revert_commit should call git revert and push."""
    with patch.object(git, "_run_git") as mock:
        mock.return_value = MagicMock(returncode=0, stdout="", stderr="")
        ok, reason = git.revert_commit("abc123")
        assert ok
        calls = [c[0] for c in mock.call_args_list]
        assert ("revert", "--no-edit", "abc123") in calls
        assert ("push",) in calls


def test_get_head_sha(git: VaultGit) -> None:
    """get_head_sha should return stripped stdout."""
    with patch.object(git, "_run_git") as mock:
        mock.return_value = MagicMock(returncode=0, stdout="abc123def\n")
        assert git.get_head_sha() == "abc123def"
