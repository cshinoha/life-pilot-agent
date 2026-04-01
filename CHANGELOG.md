# Changelog

All notable changes to this project will be documented in this file.

## [2.0.0] -- 2026-04-01

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

## [1.1.0] -- 2026-03-01

- Coach Mode with conversation history
- Process Goals integration in GROW
- Scheduler conflict resolution (monthly vs weekly GROW)

## [1.0.0] -- 2026-02-15

- Initial release: voice capture, daily processing, GROW protocol, Todoist/Calendar integration
