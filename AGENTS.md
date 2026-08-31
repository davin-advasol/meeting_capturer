# Meeting Capturer

Web app that ingests one recorded meeting and produces a diarized transcript,
structured notes, and a Q&A chat over the transcript. FastAPI backend +
React (Vite/TypeScript) frontend. Transcription and LLM providers sit behind
swappable interfaces selected by config.

## Map (this file is the only one loaded automatically — everything else is below)

- Design spec: `docs/superpowers/specs/2026-06-15-meeting-capturer-v1-design.md`
- Implementation plan, task-by-task: `docs/superpowers/plans/2026-06-15-meeting-capturer-v1.md`
- Build progress ledger (which tasks are done): `.superpowers/sdd/progress.md`
- Backend code: `backend/app/` — tests: `backend/tests/`
- Test lessons: `LESSONS.md`

## Test harness

- pytest runs as a Stop hook at the end of each turn; a failing suite blocks the
  turn until tests pass, and a blocked turn is expected when tests fail. The hook
  runs a test only once its implementation file exists, so tests for not-yet-built
  modules are skipped rather than failed.
- When the suite is red, use the `test-triage` subagent
  to diagnose instead of reading full tracebacks inline.
- Durable, hard-won test facts live in `LESSONS.md` — read it when a failure is
  confusing.

## Conventions

- Backend commands run from `backend/`.
- The user handles all git themselves — do not run git commands.
