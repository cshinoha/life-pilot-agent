---
type: note
title: Phase 2: EXECUTE
last_accessed: 2026-02-26
relevance: 0.98
tier: active
---
# Phase 2: EXECUTE

Read capture.json from Phase 1. Create TaskNotes task files, save thoughts, update CRM.

## Input
- `.session/capture.json` — output from Phase 1
- `business/_index.md` — business context
- `projects/_index.md` — projects context

## Task

### 1. Create TaskNotes task files

For each entry with `classification: "task"`:

Create markdown files in `TaskNotes/Tasks/` with frontmatter:

```yaml
title: ...
status: open
due: YYYY-MM-DD
priority: p1|p2|p3|p4
created: YYYY-MM-DDTHH:MM:SS
```

Record created task paths/IDs.

### 2. Check process goals

Read existing task notes with `contexts: [process-goal]`.

If missing or stale → create from goals.

### 3. Save thoughts

For each entry with classification idea/reflection/learning/project:
- Create file in `thoughts/{category}/YYYY-MM-DD-slug.md`
- Include frontmatter with description field (retrieval filter, ~150 chars)
- Add wiki-links to related entities
- Add typed relationships in Related section:
  ```markdown
  ## Related
  - [[business/crm/acme-corp|Acme Corp]] — context: discussed during project review
  ```

### 4. Update CRM

For entries with `classification: "crm_update"`:
- Update relevant `business/crm/*.md` or `projects/clients/*.md`
- Update deal_status, status, or add notes

### 5. Build links

For all created/updated files:
- Search for related notes in vault
- Add wiki-links with context phrases
- Update frontmatter `related:[]`

### 6. Check workload

Read active task notes due in the next 7 days.

## File write retry algorithm

```
1. Write the markdown file
2. Error? Re-read directory and retry once
3. If it still fails — report the exact file error
```

NEVER say "MCP unavailable" or mention Todoist.

## Output Format

Print ONLY valid JSON:

```json
{
  "tasks_created": [
    {"id": "tn-123abc456def", "path": "TaskNotes/Tasks/2026-02-19-follow-up-acme.md", "content": "Follow-up Acme Corp", "priority": "p2", "due": "2026-02-20"}
  ],
  "thoughts_saved": [
    {"path": "thoughts/ideas/2026-02-19-layered-memory.md", "title": "AI agents need layered memory", "category": "ideas"}
  ],
  "crm_updated": [
    {"path": "business/crm/acme-corp.md", "change": "Added meeting note"}
  ],
  "links_created": [
    {"from": "thoughts/ideas/2026-02-19-layered-memory.md", "to": "business/crm/acme-corp.md", "context": "discussed during project review"}
  ],
  "process_goals": {
    "active": 5,
    "overdue": 1,
    "created": 0
  },
  "workload": {
    "mon": 3, "tue": 2, "wed": 4, "thu": 1, "fri": 2, "sat": 0, "sun": 0
  },
  "observations": []
}
```
