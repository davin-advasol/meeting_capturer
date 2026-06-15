# Meeting Capturer — v1 Design (Recorded Mode)

**Date:** 2026-06-15
**Status:** Approved design, pre-implementation
**Scope:** v1 = recorded-meeting mode only ("Mode A"). Live goal-tracking ("Mode B") is out of scope for v1 but the architecture must not preclude it.

---

## 1. Overview

A web app that ingests **one recorded meeting at a time** and produces:

1. A diarized, timestamped **transcript**.
2. Structured **notes**: summary, action items, key decisions, topic timeline, open questions/problems.
3. A **Q&A chat** over the meeting, answered with the full transcript in context.

The transcription provider and the LLM provider are both **swappable** behind interfaces. Defaults: OpenAI `gpt-4o-transcribe-diarize` for transcription; a latest Claude model (via LangChain) for notes and Q&A.

### Explicitly out of scope for v1 (YAGNI)
- Live/streaming meetings and real-time goal/question matching (Mode B).
- A persistent library of many meetings / cross-meeting search.
- Direct SharePoint/OneDrive integration (user supplies a local file; a synced OneDrive folder appears as local).
- RAG / embeddings (a 1-hour transcript fits comfortably in modern context windows; see §7).
- Screen/visual capture (the longer-term "screen-aware" vision).
- Named-speaker identification via reference clips (designed for, not built — see §5.2).

---

## 2. Architecture

```
React (Vite) UI  ──HTTP / poll──►  FastAPI backend
  Upload                              POST /meetings            -> save file, create job, return job_id
  Progress                            GET  /meetings/{id}/status-> { stage, percent, error }
  Notes + Transcript                  GET  /meetings/{id}       -> transcript + notes
  Q&A chat                            POST /meetings/{id}/ask   -> answer (full transcript in context)
                                      GET  /meetings/{id}/qa    -> chat history

Background worker (per job):
  1. ffmpeg extract audio  ->  2. Transcriber.transcribe()  ->  3. LLM notes  ->  4. store result

Swap points (interfaces):
  - Transcriber  (default: OpenAI gpt-4o-transcribe-diarize; future: Deepgram / AssemblyAI / Whisper)
  - LLM          (LangChain chat model; default: latest Claude; switchable to OpenAI etc.)

Storage: per-meeting folder of files on disk (no DB server in v1).
```

### 2.1 Components

**Frontend — React + Vite**
- **Upload view** — drag/drop or browse a local file; client-side validation of type/size; a **"Trim silence (cheaper transcription)"** toggle (default OFF, see §5.4) sent with the upload.
- **Progress view** — polls `GET /meetings/{id}/status`; shows stages: `Uploaded → Extracting audio → Transcribing & diarizing → Generating notes → Done` with percent.
- **Results view** — tabs:
  - **Notes** — rendered from `notes.json`: summary (prose), action items (checklist with owner/due), decisions (list), topic timeline (clickable list — clicking a topic scrolls the transcript to the matching segment, anchored on segment `id` rather than wall-clock time), open questions (list). Includes an **Export / Copy Markdown** action backed by `notes.md`.
  - **Transcript** — rendered from `transcript.json`: consecutive same-speaker segments grouped into turns, `start` shown as `mm:ss`.
- **Q&A chat** — sends questions to `POST /meetings/{id}/ask`; renders answers with speaker/timestamp citations when present; history from `qa.json`.

**Backend — FastAPI (Python)**
- REST endpoints listed above.
- **In-process background task** (FastAPI `BackgroundTasks` / worker thread) runs the 4-stage pipeline and writes status after each stage. No Redis/Celery in v1 (can graduate later — see §9).
- Two provider interfaces (`Transcriber`, `LLM`) with adapters selected by config.

**Storage — files on disk (no DB server)**
- A configurable `DATA_DIR` (default `./data` at the backend project root). May point at any path, including a synced OneDrive/SharePoint folder.

---

## 3. Storage Layout

Each meeting gets one folder keyed by a generated `meeting_id`:

```
DATA_DIR/{meeting_id}/
  source/<original-filename>   # original upload, kept for re-processing
  audio.wav                    # ffmpeg-extracted, mono 16 kHz
  job.json                     # { status, stage, percent, error, timestamps }
  transcript.json              # canonical diarized transcript (§4)
  notes.json                   # structured notes — source of truth (§6)
  notes.md                     # notes rendered to Markdown for export
  qa.json                      # [{ question, answer, citations }, ...]
```

**Write ordering (failure-resilient):** `audio.wav` → `transcript.json` (+ status `transcribed`) → `notes.json` + `notes.md` (+ status `done`). A failure during notes still leaves a usable transcript on disk.

**Retention:** folders are **kept** after a new upload (files are cheap and safe to retain; a meeting can be re-opened by id). A "clear/delete" action is a later nicety, not v1.

**Frontend never reads the disk** — it always goes through the backend (`GET /meetings/{id}`). The files are the backend's source of truth.

---

## 4. Canonical Transcript Format

Every transcription provider's output is normalized into this provider-agnostic shape, so swapping providers never changes downstream code or stored format. The OpenAI default maps essentially 1:1; other adapters map into it.

```json
// DATA_DIR/{meeting_id}/transcript.json
{
  "meeting_id": "a1b2c3",
  "source_file": "weekly-sync.mp4",
  "duration_sec": 3501.2,
  "language": "en",
  "provider": "openai:gpt-4o-transcribe-diarize",
  "created_at": "2026-06-15T10:32:00Z",
  "speakers": ["Speaker 1", "Speaker 2", "Speaker 3"],
  "segments": [
    { "id": 0, "speaker": "Speaker 1", "start": 0.00, "end": 4.20, "text": "Okay, let's get started." },
    { "id": 1, "speaker": "Speaker 2", "start": 4.55, "end": 9.80, "text": "I pushed the fix last night." }
  ]
}
```

- `start` / `end` are seconds (floats). `speakers` is the distinct set of labels present.
- The UI formats `start` as `mm:ss` and groups consecutive same-speaker segments into turns.
- **Timestamps are best-effort, not load-bearing in v1.** No feature seeks an original media player, so transcript navigation (e.g. clicking a topic) anchors on **segment `id`**, not wall-clock time. When silence-trimming (§5.4) is ON, `start`/`end` reflect the *trimmed* timeline and are slightly offset from the original recording — acceptable because nothing in v1 depends on original-timeline accuracy. (A future media player with seek would require either leaving trim OFF or adding timestamp remapping; deferred.)

---

## 5. Transcription

### 5.1 Interface

```
Transcriber.transcribe(audio_path: Path, language: str | None) -> Transcript
```

`Transcript` is the canonical structure in §4. Each adapter is responsible for mapping its provider's native response into it. Provider chosen by config (`TRANSCRIBER_PROVIDER`).

### 5.2 Default adapter — OpenAI `gpt-4o-transcribe-diarize`
- Endpoint: `v1/audio/transcriptions`, model `gpt-4o-transcribe-diarize`.
- Params: `response_format="diarized_json"`, `chunking_strategy="auto"` (required for audio > 30s).
- Native output is an array of `{ speaker, start, end, text }` segments → mapped directly into canonical `segments`. Speaker labels are auto-assigned (`Speaker 1`, `Speaker 2`, …).
- Constraints to respect: no `prompt`, no `logprobs`, no `timestamp_granularities[]`.
- **Optional, deferred:** named speakers via `known_speaker_names[]` + `known_speaker_references[]` (2–10s reference clips, up to 4). Not in v1; when added, real names flow through `speaker` and into action-item owners automatically.
- Model lifecycle note: older `whisper-1` / `gpt-4o-transcribe` are retiring ~June 2026; `gpt-4o-transcribe-diarize` runs until 2027-04-16.

### 5.3 Future adapters (not built in v1)
Deepgram and AssemblyAI (both diarize natively); local Whisper. They implement the same `Transcriber` interface and normalize to §4.

### 5.4 Optional silence trimming (Silero VAD) — `vad_trim`

A pre-transcription step that physically removes long silences from `audio.wav` before upload, reducing billed audio (OpenAI bills by audio duration: ~$0.006/min or per audio-input-token, so savings ≈ silence fraction removed).

- **UI toggle** per meeting on the upload screen: *"Trim silence (cheaper transcription)"*. Default **OFF**. The chosen value is passed with the upload and recorded in `job.json`.
- **Implementation:** Silero VAD detects speech regions; only **long** silences (e.g. > 1.5s) are removed, short within-turn pauses kept (preserves diarization context). Produces a trimmed audio file fed to the `Transcriber`.
- **No timestamp remapping in v1** (see §4): when ON, stored timestamps are on the trimmed timeline. This is the deliberate simplification that makes the toggle cheap to build.
- **Magnitude:** savings are modest per meeting (a 60-min meeting ≈ $0.36; ~20% silence → ~$0.07 saved); meaningful mainly at volume or for gappy recordings. Hence default OFF.
- **Double duty:** the future local-Whisper adapter reuses Silero (via `faster-whisper`'s built-in VAD filter) for anti-hallucination on silence.
- Why not rely on OpenAI's `chunking_strategy`: that only *windows* long audio for processing — it does not drop silent regions from billing. Saving tokens requires physically trimming before upload.

---

## 6. Notes Generation

A **single structured-output LLM call** (LangChain chat model with a response schema / tool-calling) produces the whole notes object from the full transcript. The result is validated against the schema before writing. `notes.md` is then rendered from `notes.json` with a fixed template.

```json
// DATA_DIR/{meeting_id}/notes.json  (source of truth)
{
  "meeting_id": "a1b2c3",
  "model": "claude-opus-4-8",
  "generated_at": "2026-06-15T10:35:00Z",
  "summary": "The team reviewed the Q3 rollout, agreed to delay the billing migration...",
  "action_items": [
    { "owner": "Speaker 2", "task": "Ship the auth fix", "due": "2026-06-18" },
    { "owner": "Speaker 1", "task": "Draft the rollout comms", "due": null }
  ],
  "decisions": ["Delay billing migration to Q4", "Adopt feature-flag rollout for the new dashboard"],
  "topic_timeline": [
    { "start": 0.0, "topic": "Agenda & Q3 status" },
    { "start": 612.4, "topic": "Billing migration risks" }
  ],
  "open_questions": ["Who owns the data backfill?", "Is the SharePoint retention policy compatible?"]
}
```

- **Owners** are drawn from the transcript's speaker labels, so items are attributable. (Becomes real names if §5.2 is enabled later.)
- **`topic_timeline[].start`** reuses transcript seconds → clickable jump-to in the UI.
- Field text values may contain Markdown; `notes.md` is the human/export rendering (`# heading`, `- [ ]` checklists, `[mm:ss]` timeline lines).

---

## 7. Q&A

- Each question sends the **full transcript in context** to the LLM (one ~1-hour meeting ≈ 15–20k tokens worst case — well within any modern model's ≥128k window, including OpenAI). No RAG in v1.
- **Prompt caching** keeps follow-up questions cheap (the transcript is cached; each question pays full price only for the new question plus a discounted cache-read of the transcript).
- Answers should cite speaker/timestamp where the supporting evidence exists; chat history persisted to `qa.json`.
- **Forward path:** the LLM layer is structured so a retrieval step could be inserted later (only if a meeting library or multi-hour recordings are added). Not built now.

---

## 8. Configuration

`.env` / settings, validated at startup (fail fast on missing keys / unknown providers):

| Key | Purpose | Example |
|-----|---------|---------|
| `DATA_DIR` | Root for per-meeting folders | `./data` |
| `TRANSCRIBER_PROVIDER` | Transcription adapter | `openai` |
| `OPENAI_API_KEY` | OpenAI auth (transcription and/or LLM) | `sk-...` |
| `LLM_PROVIDER` | LangChain chat model provider | `anthropic` |
| `LLM_MODEL` | Model id | `claude-opus-4-8` |
| `ANTHROPIC_API_KEY` | Claude auth | `sk-ant-...` |

Switching providers is a config change, not a code change.

---

## 9. Error Handling

- **Upload validation:** reject unsupported types / oversized files with a clear message before any work starts.
- **ffmpeg failure:** mark job `failed` with the failing stage and message; UI offers retry.
- **Transcription / LLM API errors:** retry transient errors with backoff; on persistent failure mark job `failed` and surface the provider error. A job is **never left stuck** "in progress."
- **Schema validation failure (notes):** retry the structured-output call once; if still invalid, fail the notes stage but keep the transcript.
- **Q&A failure:** return an error message in the chat without losing prior history.
- All adapter calls run under a timeout. Config (keys, provider names) validated at startup.

---

## 10. Testing

- **Unit:** pipeline stages with a **fake `Transcriber`** and **fake `LLM`** (deterministic, no network); notes-schema parsing/validation; job status transitions; `notes.md` rendering from `notes.json`.
- **Adapter contract tests:** per adapter, against recorded/mocked provider responses, asserting correct normalization into the canonical format.
- **API tests:** endpoint behavior including the full job lifecycle and each failure path.
- **Frontend:** component tests for upload / progress / results / Q&A; one happy-path integration against a mocked backend.
- **Smoke test:** a tiny bundled sample audio clip exercises the real pipeline end-to-end (guarded so it can run with or without live API keys).

---

## 11. Module Boundaries (for implementation)

Each unit has one purpose, a clear interface, and is independently testable:

- `transcription/` — `Transcriber` interface + adapters (OpenAI default). In: audio path. Out: canonical `Transcript`.
- `notes/` — notes generator (LLM + schema) + `notes.md` renderer. In: `Transcript`. Out: `Notes` object + Markdown.
- `qa/` — question answering over a transcript. In: `Transcript` + question (+ history). Out: answer + citations.
- `pipeline/` — orchestrates ffmpeg → transcription → notes; owns job status writes.
- `storage/` — read/write the per-meeting folder (swappable to SQLite later behind this accessor).
- `api/` — FastAPI routes; thin, delegates to the above.
- `llm/` — LangChain chat-model factory (provider/model from config), shared by `notes` and `qa`.
- `web/` — React app (upload, progress, results, Q&A).
