---
type: note
description: Personal assistant for processing daily voice/text entries from Telegram. Classifies content, creates TaskNotes task files aligned with goals, saves thoughts to Obsidian with wiki-links, generates HTML reports. Integrates Your Business context (clients, projects, CRM). Triggers on /process command or daily 21:00 cron.
last_accessed: 2026-02-26
relevance: 0.98
tier: active
name: life-pilot-processor
depends_on: [graph-builder, agent-memory, vault-health]
---

# Life Pilot Processor

Process daily entries → tasks (TaskNotes) + thoughts (Obsidian) + HTML report (Telegram).

Integrates with Your Business data for business context.

## CRITICAL: Output Format

**ALWAYS return RAW HTML. No exceptions. No markdown. Ever.**

Your final output goes directly to Telegram with `parse_mode=HTML`.

Rules:
1. ALWAYS return HTML report — even if entries already processed
2. ALWAYS use the template below — no free-form text
3. NEVER use markdown syntax (**, ##, ```, -)
4. NEVER explain what you did in plain text — put it in HTML report

WRONG:
```html
<b>Title</b>
```

CORRECT:
<b>Title</b>

## TaskNotes Task Files

Все задачи живут как markdown notes в `TaskNotes/Tasks/` внутри vault.

Минимальный frontmatter для новой задачи:
- `title`
- `status: open`
- `due: YYYY-MM-DD`
- `priority: p1|p2|p3|p4`
- `created: YYYY-MM-DDTHH:MM:SS`
- optional: `projects`, `contexts`, `source`

## CRITICAL: File-Based Task Workflow

**НИКАКИХ WORKAROUNDS. НИКАКИХ "добавь вручную". РАБОТАЙ НАПРЯМУЮ С ФАЙЛАМИ VAULT.**

ЗАПРЕЩЕНО:
- Упоминать Todoist или MCP
- Предлагать ручное добавление
- Делать HTTP запросы к API задач
- Выводить shell-команды для копирования

ОБЯЗАТЕЛЬНО:
- Читать существующие task notes перед созданием новой задачи
- Не создавать дубликаты активных задач
- Ставить due в ISO-формате `YYYY-MM-DD`
- Если task note создан — включить path или task ID в отчёт
- Если файловая операция не удалась — включить точную ошибку в отчёт

## Processing Flow

1. **Load personal context** — Read goals/1-yearly, goals/2-monthly, goals/3-weekly
2. **Load business context**:
   - Read `business/_index.md` — Your Business (клиенты, проекты, CRM)
   - Read `projects/_index.md` — личные проекты (если релевантно)
3. **Read daily** — daily/YYYY-MM-DD.md
4. **Check workload** — read active task notes due in the next 7 days
5. **CHECK PROCESS GOALS** — inspect task notes with `contexts: [process-goal]`
   → If empty or stale: generate from goals, create recurring tasks
6. **Process entries** — Classify → task or thought, detect business mentions
7. **Build links** — Connect notes with [[wiki-links]], link to business entities
8. **Generate HTML report** — include process goals status + business activity
9. **Log actions to daily** — append action log entry (see below)
10. **Evolve MEMORY.md** — update long-term memory if needed (see below)
11. **Capture observations** — record friction signals to handoff.md (see below)

## ОБЯЗАТЕЛЬНО: Логирование в daily/

**После ЛЮБЫХ изменений в vault — СРАЗУ пиши в `daily/YYYY-MM-DD.md`:**

Формат:
```
## HH:MM [text]
{Описание действий}

**Создано/Обновлено:**
- [[path/to/file|Name]] — описание
```

**Что логировать:**
- Создание файлов в thoughts/
- Обновление business/ или projects/
- Создание task notes (с path или task ID)
- Синхронизация с внешними системами

**Пример:**
```
## 14:30 [text]
Обработка ежедневных записей

**Создано задач:** 3
- "Follow-up Acme Corp" (id: 8501234567, p2, завтра)
- "Подготовить КП Unilever" (id: 8501234568, p2, пятница)

**Сохранено мыслей:** 1
- [[thoughts/ideas/product-launch|Product Launch]] — идея запуска
```

**Зачем:** Audit trail + контекст для будущих обработок.

## Evolve MEMORY.md (Step 10 Detail)

**ЦЕЛЬ:** Поддерживать MEMORY.md актуальным. Не добавлять, а ЭВОЛЮЦИОНИРОВАТЬ.

### Когда обновлять MEMORY.md

Проверь после обработки entries — есть ли информация достойная долгосрочной памяти?

### Write Rules: Что достойно MEMORY.md

**ПИСАТЬ:**
- Key decisions с impact (pivot, tool choice, architecture change)
- Изменения в pipeline (новый лид, закрытая сделка, изменение статуса)
- Финансовые изменения (оплаты получены, долги, новые контракты)
- Новые паттерны/инсайты (learnings)
- Изменения в Active Context (новый ONE Big Thing, Hot Projects)
- Новые ключевые контакты (с context)

**НЕ ПИСАТЬ:**
- Ежедневные мелочи (встречи, звонки без impact)
- Временные заметки (оставить в daily/)
- Дубликаты того что уже есть
- Детали проектов (оставить в business/crm/, projects/)
- Тривиальные задачи

### Как обновлять (evolve, не append)

**Принцип:** Новое ЗАМЕНЯЕТ устаревшее, не добавляется рядом.

| Ситуация | Действие |
|----------|----------|
| Новое противоречит старому | ЗАМЕНИТЬ старую информацию |
| Новое дополняет старое | Добавить в существующую секцию |
| Информация устарела | Удалить или архивировать |

**Пример 1 — Изменение статуса проекта:**
```
Old: "| Acme Corp NCP Meals | p1 | Активная разработка | $XXK |"
New info: "Acme Corp NCP Meals сдан клиенту"
→ ЗАМЕНИТЬ на: "| Acme Corp NCP Meals | ✅ | Завершён | $XXK |"
```

**Пример 2 — Новое решение:**
```
Добавить в Key Decisions таблицу:
| 2026-02-01 | Отказ от X в пользу Y | причина | impact |
```

**Пример 3 — Изменение в pipeline:**
```
Old: "| LogisticsLead | Hot | $XXK |"
New info: "LogisticsLead подписал контракт"
→ Удалить из Pipeline
→ Добавить в Hot Projects или Financial Context
```

### Секции MEMORY.md для обновления

| Секция | Когда обновлять |
|--------|-----------------|
| Active Context | Изменение ONE Big Thing, Hot Projects, Pipeline |
| Key Decisions | Новое решение с impact |
| Financial Context | Оплаты, долги, контракты |
| Key People | Новый важный контакт |
| Learnings | Новый паттерн/инсайт |
| Current Crisis | Изменение в текущей критической ситуации |

### Формат Edit

Используй Edit tool для точечных изменений:

```
Edit MEMORY.md:
old_string: "| LogisticsLead | Hot | $XXK |"
new_string: "| LogisticsLead | ✅ Signed | $XXK |"
```

### В отчёте

Если обновил MEMORY.md, добавь секцию:

```html
<b>🧠 MEMORY.md обновлён:</b>
• Active Context → Hot Projects updated
• Key Decisions → +1 новое решение
```

## Capture Observations (Step 11 Detail)

**ЦЕЛЬ:** Записывать friction signals, паттерны и идеи для улучшения системы.

### Когда записывать

После обработки проверь — были ли проблемы или наблюдения?

| Тип | Когда |
|-----|-------|
| `[friction]` | MCP tool errors, timeouts, empty daily, broken links, unexpected data |
| `[pattern]` | Повторяющийся паттерн (задачи всегда overdue, daily пустой по выходным) |
| `[idea]` | Идея для улучшения pipeline, schema, отчёта |

### Формат

Append в `vault/.session/handoff.md` секцию `## Observations`:

```markdown
## Observations
- [friction] YYYY-MM-DD: task note write failed once — retry succeeded
- [pattern] YYYY-MM-DD: daily без entries 2 дня подряд — выходные?
- [idea] YYYY-MM-DD: CRM карточки без deal_deadline = невидимые дедлайны
```

### Правила

- Одна строка на наблюдение (конкретика, не абстракции)
- Дата обязательна
- Не повторять уже записанные observations
- Когда observations ≥10 → сигнал для system improvement session

### В отчёте

Если записаны observations, добавь:

```html
<b>👁 Observations:</b>
• [friction] task note write failed once
```

---

## Process Goals Check (Step 5 Detail)

**ОБЯЗАТЕЛЬНО выполни этот шаг при каждом /process:**

### 1. Проверь существующие process goals

Read active task notes in `TaskNotes/Tasks/` and find notes with `contexts: [process-goal]` or `projects: [process-goals]`.

### 2. Если process goals ОТСУТСТВУЮТ — создай их

Читай goals файлы и генерируй process commitments:

| Goal Level | Source | Process Pattern |
|------------|--------|-----------------|
| Weekly ONE Big Thing | goals/3-weekly.md | 2h deep work ежедневно |
| Monthly Top 3 | goals/2-monthly.md | 1 action/день на приоритет |
| Yearly Focus | goals/1-yearly-*.md | 30 мин/день на стратегию |

**Создай process-goal task notes:**

- "2h deep work: [ONE Big Thing]" — priority: p2, contexts: [process-goal], due: ближайший рабочий день
- "1 outreach/день: [monthly priority]" — priority: p3, contexts: [process-goal], due: завтра
- "30 мин продуктовые идеи" — priority: p4, contexts: [process-goal], due: завтра

**Лимит:** Max 5-7 активных process goals.

### 3. Если process goals ЕСТЬ — проверь статус

- Активные (upcoming) → показать в отчёте
- Просроченные (overdue) → предупредить
- Устаревшие (не связаны с текущими целями) → рекомендовать удалить

### 4. Включи в отчёт

```html
<b>📋 Process Goals:</b>
• 2h deep work: [Client Project] → ✅ активен
• 1 outreach/день → ⚠️ просрочен
{N} активных | {M} требуют внимания
```

## Entry Format

```
## HH:MM [type]
Content
```

Types: [voice], [text], [forward from: Name], [photo]

## Business Context Integration

**ТОЧКА ВХОДА:** `business/_index.md` — читай для понимания бизнес-контекста.

### Структура:
```
business/
├── _index.md       ← Статистика, обзор
├── crm/            ← ВСЁ: компании + сделки + проекты в одном файле
├── network/        ← Структура холдинга
└── events/         ← Мероприятия
```

### Распознавание упоминаний

При обработке entries ищи упоминания клиентов и проектов:

| Паттерн | Действие |
|---------|----------|
| "звонил [Client]" | Найти `business/crm/{client}.md`, добавить связь |
| "по проекту [Client]" | Найти `business/crm/{client}.md` |
| "встреча с [Client]" | Создать задачу + связать с `business/crm/{client}.md` |
| "отправил КП для [Client]" | Связать с `business/crm/{client}.md` |

### Поиск клиента по имени

1. Имя → kebab-case: "Acme Corp" → `acme-corp`, "Bi Group" → `bi-group`
2. Искать: `business/crm/{kebab-case}.md`
3. Если не найден — fuzzy search по `grep -l "{name}" business/crm/`

### Создание связей

Когда упомянут клиент/проект, добавляй wiki-links:

**В задачу:**
```
"Follow-up [[business/crm/acme-corp|Acme Corp]] по снекам"
```

**В thought:**
```
Связано с: [[business/crm/techco|TechCo]], [[business/crm/phonebrand-smm|PhoneBrand SMM]]
```

### Приоритет задач с бизнесом

| Условие | Приоритет |
|---------|-----------|
| Клиент с priority: High + deadline | p1 |
| Активный проект (In progress) | p2 |
| Клиент с priority: High | p2 |
| Клиент с priority: Mid | p3 |
| Prospect без срочности | p4 |

## Classification

task → TaskNotes (see references/tasknotes.md)
idea/reflection/learning → thoughts/ (see references/classification.md)
client/project mention → link to Business/Projects + create task if actionable

## User Communication Style

USER: [Your name], [your profession], prefers direct Russian communication

### Speech Patterns

**Tasks (создавать в TaskNotes):**
- Starts with: "надо", "нужно", "срочно", "так", "сделать"
- Multiple actions in one sentence → SPLIT into separate tasks
- Example: "надо заполнить канал и поговорить с визионером" → 2 tasks

**Thoughts (сохранять в thoughts/):**
- Starts with: "понял что", "интересная мысль", "сегодня заметил"
- Reflections, insights, learnings
- Example: "понял что клиенты сопротивляются через страх"

**Commands (выполнять через /do):**
- Direct commands: "покажи", "перенеси", "удали"
- Not for processing, already handled

### Long Sentence Handling

CRITICAL: User speaks in long run-on sentences with multiple tasks.

Example input:
"Так нужно заполнить телеграм-канал и поговорить с визионером продумать концепцию ведения канала буквально ближайшие дни"

CORRECT processing:
1. Task: "Заполнить телеграм-канал" (p2, сегодня)
2. Task: "Поговорить с визионером о концепции канала" (p2, сегодня)

WRONG processing:
1. Task: "Заполнить телеграм-канал и поговорить с визионером..." (too long, unclear)

### Parsing Rules

1. Look for action verbs: заполнить, поговорить, сделать, найти, перенести
2. Each verb = separate task (unless grammatically connected)
3. Extract deadline if mentioned: "к среде", "буквально ближайшие дни", "срочно"
4. Default priority: p2 if aligns with goals, p3 otherwise

### Optional Prefixes

User MAY use prefixes (but usually doesn't):
- "задача:" → force task creation
- "мысль:" → force thoughts/ save
- "идея:" → thoughts/ideas/

If prefix present → ALWAYS follow it, ignore content-based classification.

## Projects Context Integration

**Точка входа:** `projects/_index.md`

### Структура:
```
projects/
├── _index.md       # Clients overview
├── clients/        # Clients
└── leads/          # Leads
```

### Распознавание упоминаний

| Паттерн | Файл |
|---------|------|
| "[Client A]" | projects/clients/{client-a}.md |
| "[Client B]" | projects/clients/{client-b}.md |
| "AI обучение", "воркшоп" | projects/ контекст |

### Отличие от Business

- **Business** = основной бизнес
- **Projects** = личные проекты (консалтинг, обучение)

Если entry упоминает AI/ML обучение — ищи в projects/ сначала.

## Contacts Context Integration

**Точка входа:** `contacts/_index.md`

### Распознавание имён в entries

Ищи паттерны:
- "созвонился с [Contact] из [Client]"
- "встреча с @username"
- "Имя Фамилия написал"

### Классификация

| Индикатор | Категория | Vault Link |
|-----------|-----------|------------|
| Known business clients | business | `business/crm/{client}` |
| AI/обучение expertise, known leads | projects | `projects/leads/{name}` |
| Остальные | personal | — |

### В отчёте

Если в entries упомянуты люди, добавь секцию:

```html
<b>👤 Упомянуто контактов:</b>
• [Contact Name] (business → [[business/crm/acme-corp]])
• [Contact Name] (personal)
```

## Priority Rules

p1 — Client deadline, urgent
p2 — Aligns with ONE Big Thing or monthly priority
p3 — Aligns with yearly goal
p4 — Operational, no goal alignment

## Process Goals Preference

When creating tasks, prefer PROCESS over OUTCOME formulations.

**Outcome (less effective):**
- "Закрыть сделку с X"
- "Запустить продукт"
- "Подготовить программу"

**Process (more effective):**
- "Отправить follow-up клиенту X" (actionable, controllable)
- "2h deep work на MVP" (time-bounded)
- "Показать драфт программы коллеге" (checkpoint)

**When to transform:**
- Entry sounds vague/outcome-focused → make it specific/process-focused
- User says "нужно сделать X" → create actionable next step, not X itself
- Goal mentioned → create task that MOVES TOWARD goal, not goal itself

See: references/process-goals.md for patterns and examples.

## Thought Categories

idea → thoughts/ideas/
reflection → thoughts/reflections/
project → thoughts/projects/
learning → thoughts/learnings/

## HTML Report Template

Output RAW HTML (no markdown, no code blocks):

📊 <b>Обработка за {DATE}</b>

<b>🎯 Текущий фокус:</b>
{ONE_BIG_THING}

<b>📓 Сохранено мыслей:</b> {N}
• {emoji} {title} → {category}/

<b>✅ Создано задач:</b> {M}
• {task} <i>({priority}, {due})</i>

<b>🏢 Business Activity:</b>
• {client} — {action}
• {project} — {status update}
<i>Упомянуто клиентов: {N} | Проектов: {M}</i>

<b>📋 Process Goals:</b>
• {process goal 1} → {status}
• {process goal 2} → {status}
{N} активных | {M} требуют внимания
<i>Создано новых: {K}</i>

<b>📅 Загрузка на неделю:</b>
Пн: {n} | Вт: {n} | Ср: {n} | Чт: {n} | Пт: {n} | Сб: {n} | Вс: {n}

<b>⚠️ Требует внимания:</b>
• {overdue or stale goals}

<b>🔗 Новые связи:</b>
• [[Note A]] ↔ [[Note B]]

<b>⚡ Топ-3 приоритета:</b>
1. {task}
2. {task}
3. {task}

<b>📈 Прогресс:</b>
• {goal}: {%} {emoji}

<b>🧠 MEMORY.md:</b>
• {section} → {change description}
<i>(если обновлено)</i>

---
<i>Обработано за {duration}</i>

## If Already Processed

If all entries have `<!-- ✓ processed -->` marker, return status report:

📊 <b>Статус за {DATE}</b>

<b>🎯 Текущий фокус:</b>
{ONE_BIG_THING}

<b>📋 Process Goals:</b>
• {process goal 1} → {status}
• {process goal 2} → {status}
{N} активных | {M} требуют внимания

<b>📅 Загрузка на неделю:</b>
Пн: {n} | Вт: {n} | Ср: {n} | Чт: {n} | Пт: {n} | Сб: {n} | Вс: {n}

<b>⚠️ Требует внимания:</b>
• {overdue count} просроченных
• {today count} на сегодня

<b>⚡ Топ-3 приоритета:</b>
1. {task}
2. {task}
3. {task}

---
<i>Записи уже обработаны ранее</i>

## Allowed HTML Tags

<b> — bold (headers)
<i> — italic (metadata)
<code> — commands, paths
<s> — strikethrough
<u> — underline
<a href="url">text</a> — links

## FORBIDDEN in Output

NO markdown: **, ##, -, *, backticks
NO code blocks (triple backticks)
NO tables
NO unsupported tags: div, span, br, p, table

Max length: 4096 characters.

## References

Read these files as needed:
- references/about.md — User profile, decision filters
- references/classification.md — Entry classification rules
- references/tasknotes.md — Task file format + scheduling patterns
- references/goals.md — Goal alignment logic
- references/process-goals.md — Process vs outcome goals, transformation patterns
- references/links.md — Wiki-links building
- references/rules.md — Mandatory processing rules
- references/report-template.md — Full HTML report spec
- references/contacts.md — Contacts search and classification

## Business Quick Reference

**Точка входа:** `business/_index.md`

**Поиск клиента:**
```
grep -l "Acme Corp" business/crm/
→ business/crm/acme-corp.md
```

**Активные сделки:**
```
grep -l "deal_status:" business/crm/
```

**High priority клиенты:**
```
grep -l "priority: High" business/crm/
```

**Frontmatter полей:**
- type: crm
- industry, priority, status, region, owner, responsible
- deal_status, deal_deadline (для активных сделок)
- updated

## Relevant Skills

- [[vault/.claude/skills/graph-builder/SKILL|graph-builder]] — Vault graph analysis
- [[vault/.claude/skills/graph-builder/SKILL|graph-builder]] — use when linking tasks to business entities
