# 1. In-terminal TUI, not a web app

Date: 2026-08-31
Status: Accepted (supersedes the 2026-06-15 web-app design)

## Context

The original v1 design was a FastAPI backend + React/Vite frontend. In practice
this is a single-user tool the author runs on their own Windows machine for their
own meetings. A browser UI, an HTTP layer, polling endpoints, CORS, a dev server,
and a separate frontend build are all machinery in service of a
multi-user/remote-access story that does not exist here.

## Decision

Build a single-process **Textual TUI** in Python. No HTTP server, no browser, no
JavaScript. The three views (Transcript, Notes, Chat) become panes/tabs on a
Meeting screen; the home screen is a meeting list. Processing runs as an async
task on the Textual event loop.

## Consequences

- One language, one process, one `uv`-managed package (`meetcap/`), one entry
  point. No frontend toolchain.
- Progress and status render into list rows instead of a polled `/status`
  endpoint. `job.json` on disk is still the source of truth.
- No remote access, no concurrent users — acceptable and intended. A single
  instance lock prevents two copies double-spending.
- If a shareable/remote UI is ever needed, the `pipeline` / `storage` / `llm` /
  `transcription` packages are UI-agnostic and a web layer could be added over
  them. The TUI is the only thing thrown away in that scenario.
- Terminal constraints: no clickable media player, so transcript navigation
  anchors on segment `id`, not wall-clock time (carried from the old design).
