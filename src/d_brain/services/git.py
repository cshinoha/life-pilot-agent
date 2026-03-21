"""Git automation service for vault."""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class VaultGit:
    """Service for git operations on vault."""

    def __init__(self, vault_path: Path) -> None:
        self.vault_path = Path(vault_path)

    def _run_git(self, *args: str) -> subprocess.CompletedProcess[str]:
        """Run git command in vault directory."""
        return subprocess.run(
            ["git", *args],
            cwd=self.vault_path,
            capture_output=True,
            text=True,
            check=False,
        )

    def get_status(self) -> str:
        """Get git status."""
        result = self._run_git("status", "--porcelain")
        return result.stdout

    def has_changes(self) -> bool:
        """Check if there are uncommitted changes."""
        return bool(self.get_status().strip())

    def commit_changes(self, message: str) -> bool:
        """Stage all changes and commit.

        Args:
            message: Commit message

        Returns:
            True if commit was made, False otherwise
        """
        if not self.has_changes():
            logger.info("No changes to commit")
            return False

        # Stage vault content only (never .env or other sensitive files)
        add_result = self._run_git(
            "add",
            "daily/",
            "goals/",
            "thoughts/",
            "reflections/",
            "summaries/",
            "attachments/",
            "sessions/",
            "templates/",
            "MEMORY.md",
            ".obsidian/",
        )
        if add_result.returncode != 0:
            logger.error("Git add failed: %s", add_result.stderr)
            return False

        # Commit
        commit_result = self._run_git("commit", "-m", message)
        if commit_result.returncode != 0:
            logger.error("Git commit failed: %s", commit_result.stderr)
            return False

        logger.info("Committed: %s", message)
        return True

    def push(self) -> tuple[bool, str]:
        """Push to remote.

        Returns:
            Tuple of (success, reason).
        """
        result = self._run_git("push")
        if result.returncode != 0:
            reason = result.stderr.strip() or f"exit code {result.returncode}"
            logger.error("Git push failed: %s", reason)
            return False, reason

        logger.info("Pushed to remote")
        return True, ""

    def get_head_sha(self) -> str:
        """Get current HEAD commit SHA."""
        result = self._run_git("rev-parse", "HEAD")
        return result.stdout.strip()

    def revert_commit(self, sha: str) -> tuple[bool, str]:
        """Revert a specific commit and push.

        Args:
            sha: Commit SHA to revert.

        Returns:
            Tuple of (success, reason).
        """
        result = self._run_git("revert", "--no-edit", sha)
        if result.returncode != 0:
            reason = result.stderr.strip() or f"exit code {result.returncode}"
            logger.error("Git revert failed: %s", reason)
            return False, reason

        logger.info("Reverted commit %s", sha[:8])
        return self.push()

    def commit_and_push(self, message: str) -> tuple[bool, str]:
        """Commit all changes and push.

        Args:
            message: Commit message

        Returns:
            Tuple of (success, reason). No changes is not an error.
        """
        if self.commit_changes(message):
            return self.push()
        return True, ""
