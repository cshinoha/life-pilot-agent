"""Todoist API service — single source for all Todoist HTTP calls."""

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


class TodoistService:
    """Thin wrapper around Todoist REST API v1."""

    BASE_URL = "https://api.todoist.com/api/v1"

    def __init__(self, api_key: str, timeout: int = 10) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self._headers = {"Authorization": f"Bearer {api_key}"}

    # ── Read ────────────────────────────────────────────────────────

    def fetch_active_tasks(self) -> list[dict[str, Any]]:
        """Fetch all active tasks with cursor-based pagination."""
        if not self.api_key:
            logger.warning("Todoist API key not configured")
            return []

        all_tasks: list[dict[str, Any]] = []
        cursor: str | None = None

        try:
            while True:
                params: dict[str, str] = {}
                if cursor:
                    params["cursor"] = cursor
                resp = requests.get(
                    f"{self.BASE_URL}/tasks",
                    headers=self._headers,
                    params=params,
                    timeout=15,
                )
                if resp.status_code != 200:
                    logger.error(
                        "Todoist API error %s: %s",
                        resp.status_code,
                        resp.text[:300],
                    )
                    return all_tasks
                data = resp.json()
                all_tasks.extend(data.get("results", []))
                cursor = data.get("next_cursor")
                if not cursor:
                    break
        except Exception as e:
            logger.error("Todoist API request failed: %s", e)

        return all_tasks

    def fetch_completed_today(self, today_str: str) -> int:
        """Return count of tasks completed on *today_str* (YYYY-MM-DD)."""
        if not self.api_key:
            return 0

        try:
            resp = requests.get(
                f"{self.BASE_URL}/tasks/completed/by_completion_date",
                headers=self._headers,
                params={
                    "since": f"{today_str}T00:00:00",
                    "until": f"{today_str}T23:59:59",
                },
                timeout=15,
            )
            if resp.status_code == 200:
                return len(resp.json().get("items", []))
            logger.error(
                "Todoist completed API error %s: %s",
                resp.status_code,
                resp.text[:300],
            )
        except Exception as e:
            logger.error("Todoist completed API request failed: %s", e)
        return 0

    # ── Write ───────────────────────────────────────────────────────

    def move_to_next_monday(self, task_id: str) -> tuple[bool, str]:
        """Reschedule task to next Monday.

        Returns:
            Tuple of (success, error_description). On success error is "".
        """
        try:
            resp = requests.post(
                f"{self.BASE_URL}/tasks/{task_id}",
                headers=self._headers,
                json={"due_string": "next monday"},
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                return (True, "")
            err = f"HTTP {resp.status_code}: {resp.text[:200]}"
            logger.error("Todoist move failed: %s", err)
            return (False, err)
        except Exception as e:
            logger.error("Todoist move failed: %s", e)
            return (False, str(e))

    def delete_task(self, task_id: str) -> tuple[bool, str]:
        """Delete a task.

        Returns:
            Tuple of (success, error_description). On success error is "".
        """
        try:
            resp = requests.delete(
                f"{self.BASE_URL}/tasks/{task_id}",
                headers=self._headers,
                timeout=self.timeout,
            )
            if resp.status_code == 204:
                return (True, "")
            err = f"HTTP {resp.status_code}: {resp.text[:200]}"
            logger.error("Todoist delete failed: %s", err)
            return (False, err)
        except Exception as e:
            logger.error("Todoist delete failed: %s", e)
            return (False, str(e))

    def close_task(self, task_id: str) -> tuple[bool, str]:
        """Mark task as completed.

        Returns:
            Tuple of (success, error_description). On success error is "".
        """
        try:
            resp = requests.post(
                f"{self.BASE_URL}/tasks/{task_id}/close",
                headers=self._headers,
                timeout=self.timeout,
            )
            if resp.status_code == 204:
                return (True, "")
            err = f"HTTP {resp.status_code}: {resp.text[:200]}"
            logger.error("Todoist close failed: %s", err)
            return (False, err)
        except Exception as e:
            logger.error("Todoist close failed: %s", e)
            return (False, str(e))

    def update_content(self, task_id: str, content: str) -> tuple[bool, str]:
        """Update task content (reformulation).

        Returns:
            Tuple of (success, error_description). On success error is "".
        """
        try:
            resp = requests.post(
                f"{self.BASE_URL}/tasks/{task_id}",
                headers=self._headers,
                json={"content": content},
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                return (True, "")
            err = f"HTTP {resp.status_code}: {resp.text[:200]}"
            logger.error("Todoist update content failed: %s", err)
            return (False, err)
        except Exception as e:
            logger.error("Todoist update content failed: %s", e)
            return (False, str(e))

    def reschedule_to_today(self, task_id: str) -> tuple[bool, str]:
        """Reschedule a task to today.

        Returns:
            Tuple of (success, error_description). On success error is "".
        """
        try:
            resp = requests.post(
                f"{self.BASE_URL}/tasks/{task_id}",
                headers=self._headers,
                json={"due_string": "today"},
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                return (True, "")
            err = f"HTTP {resp.status_code}: {resp.text[:200]}"
            logger.warning("Failed to reschedule task %s: %s", task_id, err)
            return (False, err)
        except Exception as e:
            logger.warning("Failed to reschedule task %s: %s", task_id, e)
            return (False, str(e))
