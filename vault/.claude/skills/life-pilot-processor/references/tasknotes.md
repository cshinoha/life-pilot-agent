---
type: note
title: TaskNotes Integration
last_accessed: 2026-04-19
relevance: 0.84
tier: warm
---
# TaskNotes Integration

## Directory

All active tasks live in `TaskNotes/Tasks/` inside the vault.

Each task is a markdown note with YAML frontmatter.

## Required Frontmatter

```yaml
title: Follow-up Acme Corp
status: open
due: 2026-04-22
priority: p2
projects:
  - client-work
contexts:
  - process-goal
created: 2026-04-19T14:30:00
source: daily/2026-04-19.md
```

## Pre-Creation Checklist

### 1. Check Duplicates

Before creating a task note:
1. Read active task notes in `TaskNotes/Tasks/`
2. Search for similar `title`
3. If similar active task exists → do not create duplicate

### 2. Check Workload

Read active task notes due in the next 7 days.

Build workload map:
```
Mon: 2 tasks
Tue: 4 tasks  ← overloaded
Wed: 1 task
Thu: 3 tasks  ← at limit
Fri: 2 tasks
Sat: 0 tasks
Sun: 0 tasks
```

If target day has 3+ tasks → shift to the next lighter day.

## Priority Mapping

| Meaning | Value |
|---------|-------|
| Highest | p1 |
| High | p2 |
| Normal | p3 |
| Low | p4 |

## Date Rules

Store due dates as exact ISO dates: `YYYY-MM-DD`.

| Russian | Write as |
|---------|----------|
| сегодня | today's ISO date |
| завтра | tomorrow's ISO date |
| послезавтра | today + 2 days |
| на этой неделе | ближайшая пятница |
| на следующей неделе | ближайший понедельник следующей недели |

## Task Title Style

✅ Good:
- "Отправить презентацию клиенту"
- "Созвон с командой по проекту"
- "Написать пост про [тема]"

❌ Bad:
- "Подумать о презентации"
- "Что-то с клиентом"
- "Разобраться с AI"

## Body Template

```markdown
# Follow-up Acme Corp

- Source: [[daily/2026-04-19]]
- Goal alignment: [[goals/3-weekly]]
```

## Updating Existing Tasks

- Complete task: `status: done`, add `completed: YYYY-MM-DDTHH:MM:SS`
- Reformulate task: update `title` and first heading
- Reschedule task: update `due`
- Delete task: remove the markdown file

## Anti-Patterns

- ❌ Abstract tasks without next action
- ❌ Tasks without due date when a date can be inferred
- ❌ Duplicate active task notes
- ❌ Mentioning Todoist or MCP in the user-facing report
