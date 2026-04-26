"""DPV-style daily practice routines for the Life Pilot hybrid bot."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal, TypedDict, cast

import pytz

from life_pilot.config import get_settings

AnswerValue = str | list[str] | int | float | None
JsonDict = dict[str, object]
RitualName = Literal["morning", "evening"]
SessionStatus = Literal["in_progress", "completed", "abandoned", "resumable"]
SourceType = Literal["voice", "text", "system"]
WeeklyMode = Literal["summary", "deep"]

_DAILY_BLOCK_START = "<!-- life-pilot:dpv:start -->"
_DAILY_BLOCK_END = "<!-- life-pilot:dpv:end -->"
_DAILY_BLOCK_PATTERN = re.compile(
    rf"\n?{re.escape(_DAILY_BLOCK_START)}[\s\S]*?{re.escape(_DAILY_BLOCK_END)}\n?"
)


class StepDefinition(TypedDict, total=False):
    """A single DPV ritual prompt."""

    id: str
    prompt: str
    kind: Literal["text", "list", "number"]
    max_items: int
    min: int
    max: int


class RitualDefinition(TypedDict):
    """Static DPV ritual definition."""

    name: RitualName
    title: str
    start_message: str
    completed_message: str
    steps: list[StepDefinition]


class WeeklyData(TypedDict):
    """Rendered data for a weekly DPV review note."""

    mode: WeeklyMode
    week: str
    date_range: str
    generated_at: str
    average_sleep: float | None
    average_mood: float | None
    average_operability: float | None
    recurring_gratitude: list[str]
    best_moments: list[str]
    repeated_fears: list[str]
    frictions: list[str]
    improvements: list[str]
    next_focus: list[str]
    summary_narrative: list[str]
    reflection: JsonDict | None


@dataclass(slots=True)
class DpvResult:
    """Telegram-facing result for a DPV action."""

    message: str
    completed: bool = False
    file_path: Path | None = None


RITUAL_DEFINITIONS: dict[RitualName, RitualDefinition] = {
    "morning": {
        "name": "morning",
        "title": "Утренний",
        "start_message": "Начинаем утренний 6-минутный ритуал.",
        "completed_message": "Утренний ритуал завершён. Запись сохранена.",
        "steps": [
            {
                "id": "sleep",
                "prompt": "Оцени качество сна по шкале от 0 до 5 (только число).",
                "kind": "number",
                "min": 0,
                "max": 5,
            },
            {
                "id": "mood_morning",
                "prompt": "Оцени настроение сейчас по шкале от 0 до 5 (только число).",
                "kind": "number",
                "min": 0,
                "max": 5,
            },
            {
                "id": "operability",
                "prompt": (
                    "Оцени работоспособность сейчас по шкале от 0 до 5 (только число)."
                ),
                "kind": "number",
                "min": 0,
                "max": 5,
            },
            {
                "id": "gratitude",
                "prompt": "Назови одну вещь, за которую ты сегодня благодарен.",
                "kind": "list",
                "max_items": 1,
            },
            {
                "id": "fear",
                "prompt": "Какой главный страх на сегодня ты видишь?",
                "kind": "text",
            },
        ],
    },
    "evening": {
        "name": "evening",
        "title": "Вечерний",
        "start_message": "Начинаем вечерний 6-минутный ритуал.",
        "completed_message": "Вечерний ритуал завершён. Запись сохранена.",
        "steps": [
            {
                "id": "mood_evening",
                "prompt": "Оцени настроение вечером по шкале от 0 до 5 (только число).",
                "kind": "number",
                "min": 0,
                "max": 5,
            },
            {
                "id": "word_of_day",
                "prompt": "Одним словом: какое слово дня?",
                "kind": "text",
            },
            {
                "id": "event_of_day",
                "prompt": "Какое главное событие дня?",
                "kind": "text",
            },
            {
                "id": "what_worked",
                "prompt": "Что сегодня получилось?",
                "kind": "text",
            },
            {
                "id": "improve",
                "prompt": "Что можно улучшить?",
                "kind": "text",
            },
        ],
    },
}

DEEP_REVIEW_STEPS: list[dict[str, str]] = [
    {"id": "theme", "prompt": "Какая тема недели была для тебя главной?"},
    {
        "id": "key_situation",
        "prompt": "В какой ситуации это проявлялось сильнее всего?",
    },
    {
        "id": "automatic_thought",
        "prompt": "Что ты тогда говорил себе? Какая мысль крутилась в голове?",
    },
    {
        "id": "emotional_response",
        "prompt": "Что ты чувствовал и как обычно реагировал?",
    },
    {"id": "evidence_for", "prompt": "Что, как тебе кажется, подтверждает эту мысль?"},
    {
        "id": "evidence_against",
        "prompt": "А что говорит против неё или делает её не такой однозначной?",
    },
    {
        "id": "alternative_thought",
        "prompt": "Какую более точную и полезную мысль можно поставить на её место?",
    },
    {
        "id": "experiment_next_week",
        "prompt": (
            "Какой один маленький эксперимент или шаг ты хочешь сделать "
            "на следующей неделе?"
        ),
    },
]

WEEKLY_CHOICE_PROMPT = "\n".join(
    [
        "Какой формат еженедельного обзора хочешь пройти?",
        "1. Короткий обзор недели",
        "2. Глубокая рефлексия",
        "",
        "Ответь: короткий / глубокий",
    ]
)


def _now_iso() -> str:
    return datetime.now(tz=pytz.UTC).isoformat()


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\r", "\n")).strip()


def _parse_list(value: str, max_items: int = 3) -> list[str]:
    normalized = _clean(
        re.sub(r"[•▪◦-]\s+", "\n", re.sub(r"\d+[.)]\s*", "\n", value)).replace(
            ";", "\n"
        )
    )
    parts = [
        _clean(part)
        for part in re.split(r"\n|,(?=\s*[A-ZА-ЯЁ0-9])", normalized)
        if _clean(part)
    ]
    if len(parts) == 1:
        parts = [
            _clean(part) for part in re.split(r",(?=\s*\S)", normalized) if _clean(part)
        ]
    return parts[:max_items]


def _parse_number(
    value: str, min_value: int | None = None, max_value: int | None = None
) -> int | float | None:
    match = re.search(r"-?\d+(?:[,.]\d+)?", _clean(value))
    if not match:
        return None
    parsed = float(match.group(0).replace(",", "."))
    if min_value is not None and parsed < min_value:
        return None
    if max_value is not None and parsed > max_value:
        return None
    return int(parsed) if parsed.is_integer() else parsed


def _as_list(value: object | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_clean(str(item)) for item in value if _clean(str(item))]
    return [_clean(str(value))] if _clean(str(value)) else []


def _as_number(value: object | None) -> int | float | None:
    if isinstance(value, int | float):
        return value
    if isinstance(value, str):
        return _parse_number(value)
    return None


def _bullets(value: object | None) -> str:
    values = _as_list(value) if not isinstance(value, list) else value
    return "\n".join(f"- {item}" for item in values) if values else "- "


def _display_value(value: object | None) -> str:
    values = _as_list(value)
    return ", ".join(values) if values else "—"


def _display_metric(value: object | None) -> str:
    number = _as_number(value)
    return f"{number}/5" if number is not None else "—"


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _top_counts(items: list[str], limit: int = 5) -> list[str]:
    counts = Counter(_clean(item) for item in items if _clean(item))
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0].lower()))[
        :limit
    ]
    return [f"{label} ({count}×)" if count > 1 else label for label, count in ranked]


def _average(values: list[int | float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _week_id(day: date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def _week_dates(day: date) -> list[date]:
    start = day - timedelta(days=day.weekday())
    return [start + timedelta(days=offset) for offset in range(7)]


def _week_range_label(day: date) -> str:
    days = _week_dates(day)
    return f"{days[0].isoformat()} — {days[-1].isoformat()}"


def _sanitize_user_id(user_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", user_id)


def default_dpv_user_key() -> str | None:
    """Return the configured single-user DPV key for scheduled Life Pilot flows."""
    settings = get_settings()
    if not settings.allowed_user_ids:
        return None
    return f"telegram:{settings.allowed_user_ids[0]}"


def strip_dpv_daily_block(content: str) -> str:
    """Remove the rendered DPV block from a daily note for generic categorization."""
    return _DAILY_BLOCK_PATTERN.sub("\n", content).strip()


def _ritual_name(value: object) -> RitualName:
    if value == "morning":
        return "morning"
    if value == "evening":
        return "evening"
    raise ValueError(f"Unknown DPV ritual: {value}")


def _weekly_mode(value: object) -> WeeklyMode:
    if value == "deep":
        return "deep"
    return "summary"


def _int_value(value: object, default: int = 0) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _mapping(value: object) -> JsonDict:
    if isinstance(value, dict):
        return cast(JsonDict, value)
    return {}


class DpvRoutineService:
    """Persistent DPV routine engine adapted to Life Pilot's vault."""

    def __init__(self, vault_path: Path) -> None:
        self.vault_path = Path(vault_path)
        self.sessions_path = self.vault_path / "sessions" / "dpv"
        self.weekly_sessions_path = self.vault_path / "sessions" / "dpv-weekly"
        self.daily_path = self.vault_path / "daily"
        self.summaries_path = self.vault_path / "summaries"
        self.timezone = pytz.timezone(get_settings().timezone)

    def today(self) -> date:
        """Return today's date in the configured Life Pilot timezone."""
        return datetime.now(self.timezone).date()

    def start_ritual(
        self,
        user_id: str,
        day: date,
        ritual: RitualName,
        source_type: SourceType = "text",
    ) -> DpvResult:
        existing = self._load_session(user_id, day, ritual)
        active = self._find_active_session(user_id, day)

        if existing and existing.get("status") == "completed":
            return DpvResult(
                f"{RITUAL_DEFINITIONS[ritual]['title']} ритуал уже завершён за сегодня."
            )

        if active and active.get("ritual") != ritual:
            return DpvResult(
                f"У тебя уже активен {active.get('ritual')}-ритуал. "
                "Используй /resume, чтобы продолжить его."
            )

        if existing and existing.get("status") != "abandoned":
            return DpvResult(
                f"Ты не закончил {ritual} ритуал за сегодня. "
                "Продолжим с последнего вопроса?\n\n"
                f"{self._current_prompt(existing)}"
            )

        session = {
            "user_id": user_id,
            "date": day.isoformat(),
            "ritual": ritual,
            "step_index": 0,
            "status": "in_progress",
            "source_type": source_type,
            "started_at": _now_iso(),
            "updated_at": _now_iso(),
            "answers": self._empty_answers(ritual),
        }
        self._save_session(session)
        self._write_daily_note(user_id, day)
        return DpvResult(
            f"{RITUAL_DEFINITIONS[ritual]['start_message']}\n\n{self._current_prompt(session)}"
        )

    def resume_ritual(self, user_id: str, day: date) -> DpvResult | None:
        session = self._find_active_session(user_id, day)
        if not session:
            return None
        ritual = str(session["ritual"])
        return DpvResult(
            f"Ты не закончил {ritual} ритуал за сегодня. "
            "Продолжим с последнего вопроса?\n\n"
            f"{self._current_prompt(session)}"
        )

    def answer_active_ritual(
        self,
        user_id: str,
        day: date,
        raw_answer: str,
        source_type: SourceType,
    ) -> DpvResult | None:
        session = self._find_active_session(user_id, day)
        if not session:
            return None

        ritual = _ritual_name(session.get("ritual"))
        step_index = _int_value(session.get("step_index", 0))
        step = RITUAL_DEFINITIONS[ritual]["steps"][step_index]
        answer = self._parse_answer(ritual, step_index, raw_answer)

        if step["kind"] == "number" and answer is None:
            return DpvResult(
                f"{step['prompt']}\n\n"
                f"Пожалуйста, введи значение {self._number_hint(step)}."
            )

        answers = _mapping(session.get("answers"))
        answers[step["id"]] = answer
        session["answers"] = answers
        session["source_type"] = source_type
        session["updated_at"] = _now_iso()

        completed = step_index >= len(RITUAL_DEFINITIONS[ritual]["steps"]) - 1
        if completed:
            session["status"] = "completed"
            session["completed_at"] = _now_iso()
        else:
            session["step_index"] = step_index + 1
            session["status"] = "in_progress"

        self._save_session(session)
        self._write_daily_note(user_id, day)

        message = (
            RITUAL_DEFINITIONS[ritual]["completed_message"]
            if completed
            else self._current_prompt(session)
        )
        return DpvResult(message, completed=completed)

    def skip_active_ritual(self, user_id: str, day: date) -> DpvResult | None:
        session = self._find_active_session(user_id, day)
        if not session:
            return None

        ritual = _ritual_name(session.get("ritual"))
        step_index = _int_value(session.get("step_index", 0))
        step = RITUAL_DEFINITIONS[ritual]["steps"][step_index]
        skipped_answer: AnswerValue = [] if step["kind"] == "list" else None

        answers = _mapping(session.get("answers"))
        answers[step["id"]] = skipped_answer
        session["answers"] = answers
        session["source_type"] = "system"
        session["updated_at"] = _now_iso()

        completed = step_index >= len(RITUAL_DEFINITIONS[ritual]["steps"]) - 1
        if completed:
            session["status"] = "completed"
            session["completed_at"] = _now_iso()
        else:
            session["step_index"] = step_index + 1
            session["status"] = "in_progress"

        self._save_session(session)
        self._write_daily_note(user_id, day)

        message = (
            RITUAL_DEFINITIONS[ritual]["completed_message"]
            if completed
            else f"Пропущено.\n\n{self._current_prompt(session)}"
        )
        return DpvResult(message, completed=completed)

    def get_daily_status(self, user_id: str, day: date) -> str:
        morning = self._load_session(user_id, day, "morning")
        evening = self._load_session(user_id, day, "evening")

        def format_session(name: RitualName, session: JsonDict | None) -> str:
            label = "утренний" if name == "morning" else "вечерний"
            if not session:
                return f"{label}: не начат"
            if session.get("status") == "completed":
                return f"{label}: завершён"
            step = _int_value(session.get("step_index", 0)) + 1
            total = len(RITUAL_DEFINITIONS[name]["steps"])
            return f"{label}: в процессе (шаг {step}/{total})"

        return "\n".join(
            [format_session("morning", morning), format_session("evening", evening)]
        )

    def get_day_context(self, user_id: str, day: date) -> str:
        """Return concise structured DPV context for coaching/planning prompts."""
        morning = self._load_session(user_id, day, "morning")
        evening = self._load_session(user_id, day, "evening")
        if not morning and not evening:
            return ""

        morning_answers = _mapping(morning.get("answers")) if morning else {}
        evening_answers = _mapping(evening.get("answers")) if evening else {}
        planning_signal = self._daily_planning_signal(morning_answers)

        lines = [f"DPV сегодня ({day.isoformat()}):"]
        if morning:
            morning_mood = _display_metric(morning_answers.get("mood_morning"))
            gratitude = _display_value(morning_answers.get("gratitude"))
            lines.extend(
                [
                    f"- Утро: {self._status_label(morning)}",
                    f"- Сон: {_display_metric(morning_answers.get('sleep'))}",
                    f"- Настроение: {morning_mood}",
                    "- Работоспособность: "
                    f"{_display_metric(morning_answers.get('operability'))}",
                    f"- Благодарность: {gratitude}",
                    f"- Страх: {_display_value(morning_answers.get('fear'))}",
                ]
            )
        if evening:
            evening_mood = _display_metric(evening_answers.get("mood_evening"))
            word_of_day = _display_value(evening_answers.get("word_of_day"))
            event_of_day = _display_value(evening_answers.get("event_of_day"))
            what_worked = _display_value(evening_answers.get("what_worked"))
            lines.extend(
                [
                    f"- Вечер: {self._status_label(evening)}",
                    f"- Вечернее настроение: {evening_mood}",
                    f"- Слово дня: {word_of_day}",
                    f"- Главное событие: {event_of_day}",
                    f"- Получилось: {what_worked}",
                    f"- Трение: {_display_value(evening_answers.get('improve'))}",
                ]
            )
        if planning_signal:
            lines.append(f"- Сигнал для планирования: {planning_signal}")
        return "\n".join(lines)

    def get_week_context(self, user_id: str, reference_day: date) -> str:
        """Return concise weekly DPV pattern context for Life Pilot prompts."""
        sessions = self._sessions_for_week(user_id, reference_day)
        if not sessions:
            return ""

        completed = [
            session for session in sessions if session.get("status") == "completed"
        ]
        data = self._build_weekly_data(user_id, reference_day, "summary", {})
        lines = [f"DPV неделя ({data['date_range']}):"]
        lines.append(f"- Завершено ритуалов: {len(completed)}/{len(sessions)} начатых")
        lines.extend(
            [
                f"- Средний сон: {_display_metric(data['average_sleep'])}",
                f"- Среднее настроение: {_display_metric(data['average_mood'])}",
                "- Средняя работоспособность: "
                f"{_display_metric(data['average_operability'])}",
            ]
        )
        if data["recurring_gratitude"]:
            lines.append(
                "- Повторяющаяся благодарность: "
                + "; ".join(data["recurring_gratitude"][:3])
            )
        if data["best_moments"]:
            lines.append("- Лучшие события: " + "; ".join(data["best_moments"][:3]))
        if data["repeated_fears"]:
            lines.append(
                "- Повторяющиеся страхи: " + "; ".join(data["repeated_fears"][:3])
            )
        if data["frictions"]:
            lines.append("- Трения: " + "; ".join(data["frictions"][:3]))
        if data["next_focus"]:
            lines.append("- Предложенный фокус: " + "; ".join(data["next_focus"][:3]))
        return "\n".join(lines)

    def has_active_dialogue(self, user_id: str, day: date) -> bool:
        """Return whether a DPV routine or weekly review is awaiting input."""
        week = _week_id(day)
        weekly = self._load_weekly_session(user_id, week)
        if weekly and weekly.get("status") not in {"completed", "abandoned"}:
            return True
        return self._find_active_session(user_id, day) is not None

    def start_weekly_review(
        self,
        user_id: str,
        reference_day: date,
        source_type: SourceType = "text",
    ) -> DpvResult:
        week = _week_id(reference_day)
        existing = self._load_weekly_session(user_id, week)
        if existing and existing.get("status") not in {"completed", "abandoned"}:
            if existing.get("mode") == "deep":
                return DpvResult(
                    "Продолжим глубокую рефлексию.\n\n"
                    f"{self._current_deep_prompt(existing)}"
                )
            return DpvResult(WEEKLY_CHOICE_PROMPT)

        session = {
            "user_id": user_id,
            "week": week,
            "reference_date": reference_day.isoformat(),
            "step_index": 0,
            "status": "in_progress",
            "source_type": source_type,
            "started_at": _now_iso(),
            "updated_at": _now_iso(),
            "mode": None,
            "answers": {},
        }
        self._save_weekly_session(session)
        return DpvResult(WEEKLY_CHOICE_PROMPT)

    def answer_weekly_review(
        self,
        user_id: str,
        reference_day: date,
        raw_answer: str,
        source_type: SourceType,
    ) -> DpvResult | None:
        week = _week_id(reference_day)
        session = self._load_weekly_session(user_id, week)
        if not session or session.get("status") in {"completed", "abandoned"}:
            return None

        normalized = _clean(raw_answer)
        if not normalized:
            if session.get("mode") is None:
                return DpvResult(WEEKLY_CHOICE_PROMPT)
            return DpvResult(self._current_deep_prompt(session))

        session["source_type"] = source_type
        session["updated_at"] = _now_iso()

        if session.get("mode") is None:
            selected = self._normalize_weekly_choice(normalized)
            if not selected:
                return DpvResult(WEEKLY_CHOICE_PROMPT)
            session["mode"] = selected
            self._save_weekly_session(session)
            if selected == "summary":
                path = self._finalize_weekly_session(session)
                return DpvResult(
                    f"Еженедельный обзор сохранён:\n{path}",
                    completed=True,
                    file_path=path,
                )
            return DpvResult(
                "\n".join(
                    [
                        "Начинаем глубокую недельную рефлексию.",
                        "Важно не торопиться — отвечай коротко, но честно.",
                        "",
                        self._current_deep_prompt(session),
                    ]
                )
            )

        step_index = _int_value(session.get("step_index", 0))
        if step_index >= len(DEEP_REVIEW_STEPS):
            path = self._finalize_weekly_session(session)
            return DpvResult(
                f"Еженедельный обзор сохранён:\n{path}", completed=True, file_path=path
            )

        step = DEEP_REVIEW_STEPS[step_index]
        answers = _mapping(session.get("answers"))
        answers[step["id"]] = normalized
        session["answers"] = answers
        completed = step_index >= len(DEEP_REVIEW_STEPS) - 1
        if completed:
            path = self._finalize_weekly_session(session)
            return DpvResult(
                f"Глубокая рефлексия завершена. Еженедельный обзор сохранён:\n{path}",
                completed=True,
                file_path=path,
            )

        session["step_index"] = step_index + 1
        self._save_weekly_session(session)
        return DpvResult(self._current_deep_prompt(session))

    def _empty_answers(self, ritual: RitualName) -> dict[str, AnswerValue]:
        return {
            step["id"]: [] if step["kind"] == "list" else None
            for step in RITUAL_DEFINITIONS[ritual]["steps"]
        }

    def _session_path(self, user_id: str, day: date, ritual: RitualName) -> Path:
        return (
            self.sessions_path
            / _sanitize_user_id(user_id)
            / f"{day.isoformat()}-{ritual}.json"
        )

    def _weekly_session_path(self, user_id: str, week: str) -> Path:
        return self.weekly_sessions_path / _sanitize_user_id(user_id) / f"{week}.json"

    def _read_json(self, path: Path) -> JsonDict | None:
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return _mapping(loaded) or None

    def _load_session(
        self, user_id: str, day: date, ritual: RitualName
    ) -> JsonDict | None:
        return self._read_json(self._session_path(user_id, day, ritual))

    def _save_session(self, session: JsonDict) -> None:
        day = date.fromisoformat(str(session["date"]))
        path = self._session_path(
            str(session["user_id"]), day, _ritual_name(session.get("ritual"))
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _load_weekly_session(self, user_id: str, week: str) -> JsonDict | None:
        return self._read_json(self._weekly_session_path(user_id, week))

    def _save_weekly_session(self, session: JsonDict) -> None:
        path = self._weekly_session_path(str(session["user_id"]), str(session["week"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _find_active_session(self, user_id: str, day: date) -> JsonDict | None:
        sessions = [
            self._load_session(user_id, day, "morning"),
            self._load_session(user_id, day, "evening"),
        ]
        active = [
            session
            for session in sessions
            if session and session.get("status") not in {"completed", "abandoned"}
        ]
        if not active:
            return None
        return sorted(
            active, key=lambda item: str(item.get("updated_at", "")), reverse=True
        )[0]

    def _status_label(self, session: JsonDict) -> str:
        if session.get("status") == "completed":
            return "завершён"
        if session.get("status") == "abandoned":
            return "отменён"
        ritual = _ritual_name(session.get("ritual"))
        step = _int_value(session.get("step_index", 0)) + 1
        total = len(RITUAL_DEFINITIONS[ritual]["steps"])
        return f"в процессе ({step}/{total})"

    def _daily_planning_signal(self, morning_answers: JsonDict) -> str:
        sleep = _as_number(morning_answers.get("sleep"))
        mood = _as_number(morning_answers.get("mood_morning"))
        operability = _as_number(morning_answers.get("operability"))
        low_signals = [
            label
            for label, value in [
                ("sleep", sleep),
                ("mood", mood),
                ("operability", operability),
            ]
            if value is not None and value <= 2
        ]
        if low_signals:
            joined = ", ".join(low_signals)
            return (
                f"низкий ресурс ({joined}); лучше меньше задач и больше восстановления"
            )
        if all(
            value is not None and value >= 4 for value in (sleep, mood, operability)
        ):
            return "высокий ресурс; хороший день для приоритетной работы"
        return ""

    def _current_prompt(self, session: JsonDict) -> str:
        ritual = _ritual_name(session.get("ritual"))
        step_index = _int_value(session.get("step_index", 0))
        return RITUAL_DEFINITIONS[ritual]["steps"][step_index]["prompt"]

    def _current_deep_prompt(self, session: JsonDict) -> str:
        step_index = _int_value(session.get("step_index", 0))
        if step_index >= len(DEEP_REVIEW_STEPS):
            return "Глубокая рефлексия уже заполнена."
        return DEEP_REVIEW_STEPS[step_index]["prompt"]

    def _parse_answer(
        self, ritual: RitualName, step_index: int, raw: str
    ) -> AnswerValue:
        step = RITUAL_DEFINITIONS[ritual]["steps"][step_index]
        if step["kind"] == "list":
            return _parse_list(raw, int(step.get("max_items", 3)))
        if step["kind"] == "number":
            return _parse_number(raw, step.get("min"), step.get("max"))
        return _clean(raw)

    def _number_hint(self, step: StepDefinition) -> str:
        min_value = step.get("min")
        max_value = step.get("max")
        if min_value is not None and max_value is not None:
            return f"от {min_value} до {max_value}"
        if min_value is not None:
            return f"не меньше {min_value}"
        if max_value is not None:
            return f"не больше {max_value}"
        return "в числовом формате"

    def _write_daily_note(self, user_id: str, day: date) -> Path:
        self.daily_path.mkdir(parents=True, exist_ok=True)
        path = self.daily_path / f"{day.isoformat()}.md"
        existing = (
            path.read_text(encoding="utf-8")
            if path.exists()
            else f"# {day.isoformat()}\n"
        )
        block = self._render_daily_block(user_id, day)
        if _DAILY_BLOCK_PATTERN.search(existing):
            content = _DAILY_BLOCK_PATTERN.sub(f"\n{block}\n", existing).rstrip() + "\n"
        else:
            content = existing.rstrip() + f"\n\n{block}\n"
        path.write_text(content, encoding="utf-8")
        return path

    def _render_daily_block(self, user_id: str, day: date) -> str:
        morning = self._load_session(user_id, day, "morning")
        evening = self._load_session(user_id, day, "evening")
        morning_answers = _mapping(morning.get("answers")) if morning else {}
        evening_answers = _mapping(evening.get("answers")) if evening else {}
        morning_mood = _display_value(morning_answers.get("mood_morning"))
        evening_mood = _display_value(evening_answers.get("mood_evening"))

        def status(session: JsonDict | None) -> str:
            if not session:
                return "не начат"
            if session.get("status") == "completed":
                return "завершён"
            return f"в процессе, шаг {_int_value(session.get('step_index', 0)) + 1}"

        return "\n".join(
            [
                _DAILY_BLOCK_START,
                "## DPV Daily Practice",
                "",
                "### Morning",
                f"- Status: {status(morning)}",
                f"- Sleep: {_display_value(morning_answers.get('sleep'))}",
                f"- Morning mood: {morning_mood}",
                f"- Operability: {_display_value(morning_answers.get('operability'))}",
                "- Gratitude:",
                _bullets(morning_answers.get("gratitude")),
                "- Fear:",
                _bullets(morning_answers.get("fear")),
                "",
                "### Evening",
                f"- Status: {status(evening)}",
                f"- Evening mood: {evening_mood}",
                f"- Word of day: {_display_value(evening_answers.get('word_of_day'))}",
                "- Event of day:",
                _bullets(evening_answers.get("event_of_day")),
                "- What worked:",
                _bullets(evening_answers.get("what_worked")),
                "- What could improve:",
                _bullets(evening_answers.get("improve")),
                _DAILY_BLOCK_END,
            ]
        )

    def _normalize_weekly_choice(self, value: str) -> WeeklyMode | None:
        normalized = value.lower()
        if normalized in {"1", "короткий", "краткий", "обзор", "summary", "short"}:
            return "summary"
        if normalized in {"2", "глубокий", "глубокая", "рефлексия", "deep"}:
            return "deep"
        return None

    def _finalize_weekly_session(self, session: JsonDict) -> Path:
        session["status"] = "completed"
        session["completed_at"] = _now_iso()
        session["updated_at"] = session["completed_at"]
        self._save_weekly_session(session)
        reference_day = date.fromisoformat(str(session["reference_date"]))
        return self._write_weekly_review(
            str(session["user_id"]),
            reference_day,
            _weekly_mode(session.get("mode")),
            _mapping(session.get("answers")),
        )

    def _sessions_for_week(self, user_id: str, reference_day: date) -> list[JsonDict]:
        sessions: list[JsonDict] = []
        for day in _week_dates(reference_day):
            for ritual in ("morning", "evening"):
                session = self._load_session(user_id, day, ritual)
                if session:
                    sessions.append(session)
        return sessions

    def _session_values(
        self,
        sessions: list[JsonDict],
        ritual: RitualName,
        key: str,
    ) -> list[str]:
        values: list[str] = []
        for session in sessions:
            if session.get("ritual") != ritual or session.get("status") != "completed":
                continue
            answers = session.get("answers", {})
            if isinstance(answers, dict):
                values.extend(_as_list(answers.get(key)))
        return values

    def _session_numbers(
        self,
        sessions: list[JsonDict],
        ritual: RitualName,
        key: str,
    ) -> list[int | float]:
        values: list[int | float] = []
        for session in sessions:
            if session.get("ritual") != ritual or session.get("status") != "completed":
                continue
            answers = session.get("answers", {})
            if isinstance(answers, dict):
                parsed = _as_number(answers.get(key))
                if parsed is not None:
                    values.append(parsed)
        return values

    def _build_weekly_data(
        self,
        user_id: str,
        reference_day: date,
        mode: WeeklyMode,
        reflection_answers: JsonDict | object,
    ) -> WeeklyData:
        sessions = self._sessions_for_week(user_id, reference_day)
        average_sleep = _average(self._session_numbers(sessions, "morning", "sleep"))
        average_mood = _average(
            self._session_numbers(sessions, "morning", "mood_morning")
            + self._session_numbers(sessions, "evening", "mood_evening")
        )
        average_operability = _average(
            self._session_numbers(sessions, "morning", "operability")
        )
        recurring_gratitude = _top_counts(
            self._session_values(sessions, "morning", "gratitude"), 5
        )
        best_moments = _unique(
            self._session_values(sessions, "evening", "event_of_day")
        )[:10]
        repeated_fears = _unique(self._session_values(sessions, "morning", "fear"))[:7]
        frictions = _unique(self._session_values(sessions, "evening", "improve"))[:7]
        improvements = _unique(
            self._session_values(sessions, "evening", "what_worked")
        )[:7]
        next_focus = (
            frictions[:3]
            if frictions
            else ["Сохранить ритм и продолжать ежедневную практику."]
        )
        summary = self._summary_narrative(
            average_sleep,
            average_mood,
            average_operability,
            recurring_gratitude,
            best_moments,
            repeated_fears,
            frictions,
            improvements,
        )
        return {
            "mode": mode,
            "week": _week_id(reference_day),
            "date_range": _week_range_label(reference_day),
            "generated_at": _now_iso(),
            "average_sleep": average_sleep,
            "average_mood": average_mood,
            "average_operability": average_operability,
            "recurring_gratitude": recurring_gratitude,
            "best_moments": best_moments,
            "repeated_fears": repeated_fears,
            "frictions": frictions,
            "improvements": improvements,
            "next_focus": next_focus,
            "summary_narrative": summary,
            "reflection": _mapping(reflection_answers) if mode == "deep" else None,
        }

    def _summary_narrative(
        self,
        average_sleep: float | None,
        average_mood: float | None,
        average_operability: float | None,
        recurring_gratitude: list[str],
        best_moments: list[str],
        repeated_fears: list[str],
        frictions: list[str],
        improvements: list[str],
    ) -> list[str]:
        lines: list[str] = []
        if (
            average_sleep is not None
            or average_mood is not None
            or average_operability is not None
        ):
            sleep = average_sleep if average_sleep is not None else "—"
            mood = average_mood if average_mood is not None else "—"
            operability = (
                average_operability if average_operability is not None else "—"
            )
            lines.append(
                "Средние метрики недели: "
                f"сон {sleep}/5, "
                f"настроение {mood}/5, "
                f"работоспособность {operability}/5."
            )
        if best_moments:
            lines.append(f"Главное событие недели: {best_moments[0]}.")
        if improvements:
            lines.append(f"Лучше всего получалось: {improvements[0]}.")
        if repeated_fears:
            lines.append(f"Повторяющийся страх недели: {repeated_fears[0]}.")
        if frictions:
            lines.append(f"Основная зона для улучшения: {frictions[0]}.")
        if recurring_gratitude:
            lines.append(
                f"Чаще всего ты отмечал благодарность за: {recurring_gratitude[0]}."
            )
        return lines

    def _write_weekly_review(
        self,
        user_id: str,
        reference_day: date,
        mode: WeeklyMode,
        reflection_answers: JsonDict | object,
    ) -> Path:
        data = self._build_weekly_data(user_id, reference_day, mode, reflection_answers)
        self.summaries_path.mkdir(parents=True, exist_ok=True)
        path = self.summaries_path / f"{data['week']}-dpv-review.md"
        path.write_text(self._render_weekly_review(data), encoding="utf-8")
        return path

    def _render_weekly_review(self, data: WeeklyData) -> str:
        average_sleep = (
            data["average_sleep"] if data["average_sleep"] is not None else "—"
        )
        average_mood = data["average_mood"] if data["average_mood"] is not None else "—"
        average_operability = (
            data["average_operability"]
            if data["average_operability"] is not None
            else "—"
        )
        lines = [
            "---",
            f"week: {data['week']}",
            f"date_range: {data['date_range']}",
            "source: dpv-review",
            f"mode: {data['mode']}",
            f"generated_at: {data['generated_at']}",
            f"average_sleep: {data['average_sleep']}",
            f"average_mood: {data['average_mood']}",
            f"average_operability: {data['average_operability']}",
            "---",
            "",
            f"# Еженедельный DPV-обзор — {data['week']}",
            "",
            "## Краткий вывод недели",
            _bullets(data["summary_narrative"]),
            "",
            "## Метрики недели",
            f"- Средний сон: {average_sleep} / 5",
            f"- Среднее настроение: {average_mood} / 5",
            f"- Средняя работоспособность: {average_operability} / 5",
            "",
            "## Повторяющаяся благодарность",
            _bullets(data["recurring_gratitude"]),
            "",
            "## Лучшие события",
            _bullets(data["best_moments"]),
            "",
            "## Повторяющиеся страхи",
            _bullets(data["repeated_fears"]),
            "",
            "## Сложности и трения",
            _bullets(data["frictions"]),
            "",
            "## Что получилось на этой неделе",
            _bullets(data["improvements"]),
            "",
            "## Фокус на следующую неделю",
            _bullets(data["next_focus"]),
        ]
        reflection = data.get("reflection")
        if isinstance(reflection, dict):
            labels = [
                ("Главная тема недели", "theme"),
                ("Ключевая ситуация", "key_situation"),
                ("Автоматическая мысль", "automatic_thought"),
                ("Эмоции и реакция", "emotional_response"),
                ("Что подтверждает эту мысль", "evidence_for"),
                ("Что ей противоречит", "evidence_against"),
                ("Более реалистичная мысль", "alternative_thought"),
                ("Эксперимент на следующую неделю", "experiment_next_week"),
            ]
            for title, key in labels:
                lines.extend(["", f"## {title}", _bullets(reflection.get(key))])
        return "\n".join(lines) + "\n"
