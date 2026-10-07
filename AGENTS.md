# Meeting Digest

Turns recorded meetings into speaker-labeled transcripts, presentation
screenshots, and evidence-linked notes, then answers questions about them.
Two Agent Skills (`skills/meeting-digest`, `skills/meeting-assistant`) plus the
local `meeting-digest` CLI they drive.

## Map (this file is the only one loaded automatically — everything else is below)

- Design spec: `docs/superpowers/specs/2026-09-24-repo-foundation-design.md`
- Implementation plan: `docs/superpowers/plans/2026-09-24-repo-foundation.md`
- Skills: `skills/` — CLI package: `src/meeting_digest/` — tests: `tests/`
- Test lessons: `LESSONS.md`

## Test harness

- pytest runs as a Stop hook at the end of each turn; a failing suite blocks the
  turn until tests pass, and a blocked turn is expected when tests fail.
- When the suite is red, use the `test-triage` subagent
  to diagnose instead of reading full tracebacks inline.
- Durable, hard-won test facts live in `LESSONS.md` — read it when a failure is
  confusing.

## Conventions

- Commands run from the repo root.
- The user handles all git themselves — do not run git commands.
