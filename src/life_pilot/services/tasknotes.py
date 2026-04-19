"""TaskNotes-backed task service using vault-local markdown files."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")
_ACTIVE_STATUSES = {
    "active",
    "backlog",
    "in-progress",
    "in_progress",
    "next",
    "open",
    "pending",
    "planned",
    "scheduled",
    "todo",
}
_DONE_STATUSES = {
    "archived",
    "cancelled",
    "canceled",
    "closed",
    "complete",
    "completed",
    "deleted",
    "done",
}
_FRONTMATTER_ORDER = [
    "title",
    "status",
    "due",
    "priority",
    "projects",
    "contexts",
    "created",
    "updated",
    "completed",
    "source",
]


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _parse_inline_list(value: str) -> list[Any]:
    inner = value[1:-1].strip()
    if not inner:
        return []
    return [_parse_scalar(part.strip()) for part in inner.split(",") if part.strip()]


def _parse_scalar(value: str) -> Any:
    stripped = value.strip()
    if not stripped:
        return ""
    if stripped.startswith("[") and stripped.endswith("]"):
        return _parse_inline_list(stripped)

    lowered = stripped.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    if re.fullmatch(r"-?\d+", stripped):
        return int(stripped)
    if re.fullmatch(r"-?\d+\.\d+", stripped):
        return float(stripped)
    return _strip_quotes(stripped)


def _parse_frontmatter(block: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    lines = block.splitlines()
    i = 0

    while i < len(lines):
        raw_line = lines[i].rstrip()
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or raw_line.startswith((" ", "\t")):
            i += 1
            continue

        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", raw_line)
        if not match:
            i += 1
            continue

        key, value_text = match.groups()
        if value_text:
            data[key] = _parse_scalar(value_text)
            i += 1
            continue

        items: list[Any] = []
        i += 1
        while i < len(lines):
            list_line = lines[i]
            list_match = re.match(r"^\s*-\s+(.*)$", list_line)
            if not list_match:
                break
            items.append(_parse_scalar(list_match.group(1)))
            i += 1
        data[key] = items

    return data


def _dump_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def _dump_frontmatter(frontmatter: dict[str, Any]) -> str:
    ordered_keys = [key for key in _FRONTMATTER_ORDER if key in frontmatter]
    ordered_keys.extend(
        sorted(key for key in frontmatter if key not in _FRONTMATTER_ORDER)
    )

    lines: list[str] = []
    for key in ordered_keys:
        value = frontmatter.get(key)
        if value is None or value == "" or value == []:
            continue

        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {_dump_scalar(item)}")
            continue

        lines.append(f"{key}: {_dump_scalar(value)}")

    return "\n".join(lines)


def _split_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    normalized = content.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return {}, normalized

    boundary = normalized.find("\n---\n", 4)
    if boundary == -1:
        return {}, normalized

    block = normalized[4:boundary]
    body = normalized[boundary + len("\n---\n") :]
    return _parse_frontmatter(block), body.lstrip("\n")


def _extract_first_date(value: Any) -> str | None:
    if value is None:
        return None
    match = _DATE_PATTERN.search(str(value))
    return match.group(0) if match else None


def _normalize_priority(value: Any) -> int:
    if isinstance(value, int):
        if 1 <= value <= 4:
            return value
        return 1

    raw = str(value).strip().lower()
    if raw in {"p1", "high", "urgent"}:
        return 4
    if raw in {"p2", "medium-high", "important"}:
        return 3
    if raw in {"p3", "medium", "normal"}:
        return 2
    if raw in {"p4", "low", "someday"}:
        return 1

    if raw.isdigit():
        number = int(raw)
        if 1 <= number <= 4:
            return number
    return 1


def _priority_to_label(priority: Any) -> str:
    normalized = _normalize_priority(priority)
    mapping = {4: "p1", 3: "p2", 2: "p3", 1: "p4"}
    return mapping.get(normalized, "p4")


def _slugify(value: str) -> str:
    slug = _SLUG_PATTERN.sub("-", value.lower()).strip("-")
    return slug or "task"


def _next_monday(from_day: date) -> date:
    days_ahead = (7 - from_day.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return from_day + timedelta(days=days_ahead)


@dataclass(slots=True)
class TaskNote:
    """Parsed markdown task note."""

    task_id: str
    path: Path
    frontmatter: dict[str, Any]
    body: str

    @property
    def title(self) -> str:
        raw_title = str(self.frontmatter.get("title", "")).strip()
        if raw_title:
            return raw_title

        for line in self.body.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
            if stripped:
                return stripped

        return self.path.stem.replace("-", " ")

    @property
    def status(self) -> str:
        return str(self.frontmatter.get("status", "open")).strip().lower()

    @property
    def due_date(self) -> str | None:
        return _extract_first_date(self.frontmatter.get("due"))

    @property
    def completed_date(self) -> str | None:
        for key in ("completed", "completed_at", "closed", "closed_at", "done"):
            completed = _extract_first_date(self.frontmatter.get(key))
            if completed:
                return completed
        return None


class TaskNotesService:
    """Manage TaskNotes-compatible markdown task files inside the vault."""

    def __init__(
        self,
        vault_path: Path,
        tasks_dir: Path | str = Path("TaskNotes/Tasks"),
    ) -> None:
        self.vault_path = Path(vault_path).resolve()
        raw_tasks_dir = Path(tasks_dir)
        self.tasks_path = (
            raw_tasks_dir.resolve()
            if raw_tasks_dir.is_absolute()
            else (self.vault_path / raw_tasks_dir).resolve()
        )
        self.tasks_path.mkdir(parents=True, exist_ok=True)

    @property
    def relative_tasks_dir(self) -> Path:
        """TaskNotes directory path relative to the vault root."""
        return self.tasks_path.relative_to(self.vault_path)

    def _iter_task_files(self) -> list[Path]:
        if not self.tasks_path.exists():
            return []
        return sorted(
            path
            for path in self.tasks_path.rglob("*.md")
            if path.is_file() and not path.name.startswith(".")
        )

    def _task_id_for_path(self, path: Path) -> str:
        rel_path = path.relative_to(self.tasks_path).as_posix()
        digest = hashlib.sha1(rel_path.encode("utf-8")).hexdigest()[:12]
        return f"tn-{digest}"

    def _read_task_note(self, path: Path) -> TaskNote:
        content = path.read_text(encoding="utf-8", errors="replace")
        frontmatter, body = _split_frontmatter(content)
        return TaskNote(
            task_id=self._task_id_for_path(path),
            path=path,
            frontmatter=frontmatter,
            body=body,
        )

    def _write_task_note(self, note: TaskNote) -> None:
        frontmatter_text = _dump_frontmatter(note.frontmatter)
        body = note.body.strip()
        if not body:
            body = f"# {note.title}"

        rendered = f"---\n{frontmatter_text}\n---\n\n{body}\n"
        note.path.parent.mkdir(parents=True, exist_ok=True)
        note.path.write_text(rendered, encoding="utf-8")

    def _replace_heading(self, body: str, title: str) -> str:
        stripped = body.strip()
        if not stripped:
            return f"# {title}"

        lines = body.splitlines()
        for index, line in enumerate(lines):
            if line.strip().startswith("# "):
                lines[index] = f"# {title}"
                return "\n".join(lines).strip()
            if line.strip():
                break
        return stripped

    def _note_to_task(self, note: TaskNote) -> dict[str, Any]:
        due_date = note.due_date
        return {
            "id": note.task_id,
            "content": note.title,
            "priority": _normalize_priority(note.frontmatter.get("priority")),
            "due": {"date": due_date} if due_date else None,
            "status": note.status,
            "path": str(note.path.relative_to(self.vault_path)),
        }

    def _is_active(self, note: TaskNote) -> bool:
        status = note.status
        if not status:
            return True
        if status in _DONE_STATUSES:
            return False
        return status in _ACTIVE_STATUSES or status not in _DONE_STATUSES

    def _find_note_by_id(self, task_id: str) -> TaskNote:
        for path in self._iter_task_files():
            note = self._read_task_note(path)
            if note.task_id == task_id:
                return note
        raise FileNotFoundError(f"Task note not found: {task_id}")

    def fetch_active_tasks(self) -> list[dict[str, Any]]:
        """Return active tasks in the runtime dictionary shape used by the bot."""
        tasks = [
            self._note_to_task(note)
            for note in (self._read_task_note(path) for path in self._iter_task_files())
            if self._is_active(note)
        ]
        return sorted(
            tasks,
            key=lambda task: (
                task.get("due", {}).get("date", "9999-12-31")
                if isinstance(task.get("due"), dict)
                else "9999-12-31",
                -int(task.get("priority", 1)),
                str(task.get("content", "")),
            ),
        )

    def fetch_completed_today(self, today_str: str) -> int:
        """Return the number of tasks completed on the provided date."""
        count = 0
        for path in self._iter_task_files():
            note = self._read_task_note(path)
            if note.status in _DONE_STATUSES and note.completed_date == today_str:
                count += 1
        return count

    def create_task(
        self,
        title: str,
        *,
        due: str | None = None,
        priority: Any = "p3",
        projects: list[str] | None = None,
        contexts: list[str] | None = None,
        body: str = "",
    ) -> dict[str, Any]:
        """Create a new task note and return it in runtime format."""
        now = datetime.now().replace(microsecond=0)
        slug = _slugify(title)[:48]
        filename = f"{now.strftime('%Y%m%d-%H%M%S')}-{slug}.md"
        path = self.tasks_path / filename

        frontmatter: dict[str, Any] = {
            "title": title,
            "status": "open",
            "priority": _priority_to_label(priority),
            "created": now.isoformat(),
        }
        if due:
            frontmatter["due"] = due
        if projects:
            frontmatter["projects"] = projects
        if contexts:
            frontmatter["contexts"] = contexts

        note = TaskNote(
            task_id=self._task_id_for_path(path),
            path=path,
            frontmatter=frontmatter,
            body=body.strip() or f"# {title}",
        )
        self._write_task_note(note)
        return self._note_to_task(note)

    def move_to_next_monday(self, task_id: str) -> tuple[bool, str]:
        """Reschedule task note to the next Monday."""
        try:
            note = self._find_note_by_id(task_id)
            note.frontmatter["due"] = _next_monday(date.today()).isoformat()
            note.frontmatter["updated"] = (
                datetime.now().replace(microsecond=0).isoformat()
            )
            self._write_task_note(note)
            return True, ""
        except Exception as exc:
            logger.error("TaskNotes move failed: %s", exc)
            return False, str(exc)

    def delete_task(self, task_id: str) -> tuple[bool, str]:
        """Delete a task note file."""
        try:
            note = self._find_note_by_id(task_id)
            note.path.unlink(missing_ok=False)
            return True, ""
        except Exception as exc:
            logger.error("TaskNotes delete failed: %s", exc)
            return False, str(exc)

    def close_task(self, task_id: str) -> tuple[bool, str]:
        """Mark a task note as done."""
        try:
            note = self._find_note_by_id(task_id)
            now = datetime.now().replace(microsecond=0).isoformat()
            note.frontmatter["status"] = "done"
            note.frontmatter["completed"] = now
            note.frontmatter["updated"] = now
            self._write_task_note(note)
            return True, ""
        except Exception as exc:
            logger.error("TaskNotes close failed: %s", exc)
            return False, str(exc)

    def update_content(self, task_id: str, content: str) -> tuple[bool, str]:
        """Update task title in frontmatter and heading."""
        try:
            note = self._find_note_by_id(task_id)
            note.frontmatter["title"] = content
            note.frontmatter["updated"] = (
                datetime.now().replace(microsecond=0).isoformat()
            )
            note.body = self._replace_heading(note.body, content)
            self._write_task_note(note)
            return True, ""
        except Exception as exc:
            logger.error("TaskNotes update content failed: %s", exc)
            return False, str(exc)

    def reschedule_to_today(self, task_id: str) -> tuple[bool, str]:
        """Reschedule a task note to today."""
        try:
            note = self._find_note_by_id(task_id)
            note.frontmatter["due"] = date.today().isoformat()
            note.frontmatter["updated"] = (
                datetime.now().replace(microsecond=0).isoformat()
            )
            self._write_task_note(note)
            return True, ""
        except Exception as exc:
            logger.warning("Failed to reschedule task %s: %s", task_id, exc)
            return False, str(exc)
