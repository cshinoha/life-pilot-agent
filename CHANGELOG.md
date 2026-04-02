# Changelog

All notable changes to this project will be documented in this file.

## [2.1.0] - 2026-04-02

### Added
- Groq Whisper transcription (replaces Deepgram) — free, 1-3 sec response time
- Healthcheck handler — vault monitoring on Wed/Sun at 22:00
- Daily plan scheduler — morning plan at 11:00 with goals + tasks context
- Coach profile compaction — monthly profile cleanup (1st at 03:00)
- Weekly goals staleness check — prompts to update goals older than 7 days
- Undo system improvements — auto-remove buttons after 5 min TTL
- Quarterly GROW sessions (Apr/Jul/Oct/Dec)
- Yearly GROW sessions (end: Dec 20/23/26, start: Jan 5/7/9)
- Google Calendar integration via MCP
- Coach model selection via COACH_MODEL env var
- Timezone configuration via TIMEZONE env var
- Full test suite (134 tests)

### Changed
- Renamed d-brain → life-pilot everywhere (package, systemd, skills, docs)
- Transcription: Deepgram → Groq Whisper (whisper-large-v3-turbo)
- Git service: explicit paths instead of `git add -A`
- Todoist service: tuple returns (success, reason)
- Config: added field_validator for ~ expansion in paths

### Fixed
- Monthly report at 20:30 (was 21:00, conflicted with GROW)
- Weekly GROW skips days 1-3 of month (monthly GROW priority)
- GROW draft deduplication on resume after restart

## [2.0.0] - 2026-04-01

### Added
- Free Chat mode (Chat button) -- direct conversation with Claude
- Zoom In/Out as explicit buttons in Coach Mode (removed auto-triggers)
- Undo button auto-removal after 5 minutes
- Healthcheck scheduler (Wed+Sun 22:00)
- 12-button keyboard (was 9)
- Complete .env.example with all variables

### Fixed
- Zoom patterns no longer trigger on random text
- Undo button no longer persists forever
- Expired undo payloads now cleaned from memory

### Changed
- Positioning: "AI Life Assistant" not just a bot
- README rewritten with full feature documentation

## [1.1.0] - 2026-03-01

- Coach Mode with conversation history
- Process Goals integration in GROW
- Scheduler conflict resolution (monthly vs weekly GROW)

## [1.0.0] - 2026-02-15

- Initial release: voice capture, daily processing, GROW protocol, Todoist/Calendar integration
