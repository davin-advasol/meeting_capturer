# Meeting Capturer — TUI Design (v1)

**Date:** 2026-08-31
**Status:** Approved design, pre-implementation
**Supersedes:** `docs/superpowers/specs/2026-06-15-meeting-capturer-v1-design.md` (web app)
**Related:** `CONTEXT.md` (glossary), `docs/adr/0001`, `docs/adr/0002`

---

## 1. Overview

A single-user, in-terminal (Textual TUI) app that ingests **one recorded meeting
at a time** and produces:

1. A diarized, timestamped **transcript**, normalized into one provider-agnostic
   shape.
2. Structured **notes**: summary, action items (owner/due), decisions, topic
   timeline, open questions — one structured-output LLM call over the full
   transcript. `notes.json` is source of truth; `notes.md` is the export
   rendering.
3. A **Q&A chat** over the meeting: each question sends the entire transcript
   (plus prior Q&A history) in context — no retrieval. Prompt caching keeps
   follow-ups cheap.

Transcription and LLM providers sit behind swappable seams selected by config.

### Out of scope for v1 (YAGNI)

- Local transcription (`faster-whisper` + `pyannote`) — seam defined, not built.
- Local LLM (`ollama`) — `init_chat_model` supports it later, not built.
- Silence trimming (Silero VAD).
- Map-reduce / chunked notes for transcripts that exceed the context window
  (v1 assumes meetings ≤ ~2 hours).
- Named-speaker identification via reference voice clips.
- Visual / video understanding — see §12 (V1.5 forward-compat only).
- Remote access, multiple users, any HTTP layer.

---

## 2. Tech Stack

- **Python 3.12+**, packaged with `uv`, `pyproject.toml`, console entry point
  `meetcap`.
- **Textual** for the TUI (panes, scrolling, async event loop). `Pilot` for TUI
  tests.
- **LangChain** (`langchain`, `langchain-openai`, `langchain-anthropic`) for the
  LLM layer via `init_chat_model`; Pydantic schema via `with_structured_output`.
- **openai** SDK for transcription (`gpt-4o-transcribe-diarize`).
- **imageio-ffmpeg** for a bundled ffmpeg binary; **ffmpeg-python** or direct
  `subprocess` for invocation.
- **watchdog** for the inbox watcher.
- **pydantic** v2 for all on-disk schemas and validation.
- **platformdirs** for config-file location; **python-dotenv** for `.env`.
- **pyperclip** for the clipboard export.
- **pytest** for tests (runs as a Stop hook per `CLAUDE.md`).

---

## 3. Package Layout

```
meetcap/
  __init__.py
  __main__.py            entry point: arg parse, single-instance lock, launch TUI
  config.py             load/validate config.toml + .env; Config dataclass
  pricing.py             price table lookup, $ estimation
  ids.py                 meeting_id generation (YYYY-MM-DD-slug, collision suffix)
  models.py              Pydantic models: Transcript, Segment, Notes, ActionItem,
                          Job, UsageRecord, SpeakerMap
  storage/
    __init__.py
    meeting_store.py     read/write a meeting folder; list meetings; locking
  audio/
    __init__.py
    extract.py           ffmpeg -> audio.wav (mono 16 kHz); duration probe
  transcription/
    __init__.py
    base.py              Transcriber protocol + register/select-by-config
    openai_diarize.py    OpenAI gpt-4o-transcribe-diarize adapter
    fakes.py              FakeTranscriber for tests
  llm/
    __init__.py
    factory.py            init_chat_model wrapper; provider/model from config
    caching.py            attach cache_control for anthropic; no-op otherwise
  notes/
    __init__.py
    schema.py             NotesLLMOutput Pydantic schema (LLM contract)
    generate.py           build prompt, call LLM, validate, map to Notes
    render.py             Notes -> notes.md
  qa/
    __init__.py
    session.py            build context bundle, stream answer, append qa.json
  pipeline/
    __init__.py
    stages.py             Stage protocol; ExtractStage, TranscribeStage, NotesStage
    runner.py            ordered stage list, status writes, retry/backoff, queue
  context_bundle.py       ContextBundle: {transcript, speaker_map} -> prompt text
  tui/
    __init__.py
    app.py                MeetcapApp (Textual App), key bindings, screen stack
    setup_wizard.py       first-run provider selection -> config.toml
    meeting_list.py       home screen: processed + pending rows, live status
    meeting_screen.py     tabbed Transcript / Notes / Chat
    transcript_view.py
    notes_view.py
    chat_view.py
    speaker_modal.py      post-transcription rename modal
    confirm_modal.py      confirm-to-process dialog
    settings_screen.py
  logging_setup.py        rotating file handler -> DATA_DIR/meetcap.log
tests/
  ...mirrors package...
  fixtures/
    openai_diarized_response.json
    azure_notes_response.json
    sample_meeting.m4a    tiny (~10s) clip for the smoke test
```

---

## 4. Configuration

### 4.1 `config.toml`

Location: `platformdirs.user_config_dir("meetcap")/config.toml`. Written by the
setup wizard, edited by the Settings screen.

```toml
[providers]
transcription = "openai"          # openai | azure-openai (azure-openai not impl in v1)
llm = "azure-openai"             # azure-openai | openai | anthropic

[llm]
model = "gpt-4o"                  # Azure deployment name, or model id for openai/anthropic

[paths]
data_dir = "~/meetcap/data"
inbox_dir = "~/meetcap/inbox"
export_dir = ""                   # blank = export-to-folder disabled (clipboard still works)

[pricing]
"openai:gpt-4o-transcribe-diarize" = { per_min = 0.006 }
"azure-openai:gpt-4o" = { in_per_1m = 2.5, out_per_1m = 10.0, cached_in_per_1m = 1.25 }
```

`~` is expanded. `data_dir` and `inbox_dir` are created if missing.

### 4.2 `.env` (secrets — never written by the app)

| Var | Needed when |
|-----|-------------|
| `OPENAI_API_KEY` | `transcription = openai` OR `llm = openai` |
| `AZURE_OPENAI_API_KEY` | `llm = azure-openai` |
| `AZURE_OPENAI_ENDPOINT` | `llm = azure-openai` |
| `AZURE_OPENAI_API_VERSION` | `llm = azure-openai` |
| `ANTHROPIC_API_KEY` | `llm = anthropic` |

Loaded from `.env` in the current working directory (fallback: `data_dir/.env`).
Startup validates that every var required by the selected providers is present
and non-empty; on any missing var the app prints the exact list and exits with
code 2 — **before** the TUI starts.

---

## 5. Storage Layout

`meeting_id = "<YYYY-MM-DD>-<slug>"` where the date is the source file's
modification date and `slug` is the filename stem lowercased, non-alphanumerics
collapsed to `-`, trimmed to 40 chars. On collision, append `-2`, `-3`, …

```
DATA_DIR/{meeting_id}/
  source/<original-filename>   original, moved in from INBOX_DIR, kept forever
  audio.wav                    ffmpeg-extracted, mono 16 kHz PCM
  job.json                     Job model (§6)
  transcript.json              Transcript model (§7)
  speaker_map.json             SpeakerMap model — optional, created by rename modal
  notes.json                   Notes model — source of truth (§8)
  notes.md                     rendered Markdown (§8.3)
  qa.json                      { turns: [QATurn], sessions: [int] } append-only (§9)
  usage.json                   UsageRecord model (§10)
  visuals.json                 V1.5 only — absent in v1
```

`DATA_DIR/meetcap.log` — rotating log (1 MB × 3). `DATA_DIR/.lock` — single
instance lock (`{ pid, started_at }`); a lock whose PID is not alive is
overwritten.

**Write ordering (failure-resilient):** `audio.wav` → `transcript.json`
(+ status `transcribed`) → `notes.json` + `notes.md` (+ status `ready`). A crash
after the transcript leaves a usable transcript and working chat.

---

## 6. Job Model & Pipeline

### 6.1 `Job` (models.py)

```python
class Job(BaseModel):
    meeting_id: str
    source_path: str                 # absolute path inside source/ once moved
    original_inbox_path: str | None   # where it came from, for logging
    status: Literal["pending", "queued", "extracting", "transcribing",
                    "generating_notes", "ready", "notes_failed", "failed"]
    stage_percent: float             # 0..100, best-effort within the current stage
    error: str | None
    created_at: datetime
    updated_at: datetime
    transcription_provider: str      # recorded at process time
    llm_provider_model: str
```

### 6.2 Pipeline

`runner.run(meeting_id)` executes an **ordered list** of stages. v1 list:
`[ExtractStage, TranscribeStage, NotesStage]`. (V1.5 inserts `VisualStage` before
`NotesStage`.)

Each `Stage` has:

```python
class Stage(Protocol):
    name: str                        # "extract" | "transcribe" | "generating_notes"
    status_while_running: str         # the Job.status to set on entry
    def run(self, ctx: PipelineContext) -> None: ...
    # may call ctx.report_percent(float)
```

- The runner sets `status`, clears `error`, writes `job.json` on every stage
  entry and on every `report_percent` call (throttled to ~1/sec).
- **Retry/backoff:** each stage's provider calls are wrapped so transient errors
  (HTTP 429, 5xx, connection/timeout) retry up to 4 times with exponential
  backoff (1s, 2s, 4s, 8s + jitter). Non-transient errors propagate immediately.
- **Failure semantics:**
  - Exception in `ExtractStage` or `TranscribeStage` → `status = "failed"`,
    `error` = message, stop.
  - Exception in `NotesStage` → `status = "notes_failed"`, `error` = message,
    stop. Transcript + chat remain usable.
- **Notes schema retry:** `NotesStage` calls the LLM; if the response fails
  Pydantic validation, it retries the call **once** with a corrective system
  message; a second failure raises (→ `notes_failed`).
- **Never stuck:** any unhandled exception in the runner task is caught, logged
  with traceback, and the job set to `failed` (or `notes_failed` if the
  transcript already exists).
- **Retry from the list screen** resumes from the first stage whose output
  artifact is missing (transcript present + notes missing → run only
  `NotesStage`).
- **Serial queue:** the TUI owns one `asyncio.Task` worker that pulls
  `meeting_id`s off an `asyncio.Queue`. Only one job runs at a time.

### 6.3 Progress granularity

| Stage | Percent source |
|-------|----------------|
| extract | ffmpeg `-progress` pipe: `out_time_us / (duration_us)` |
| transcribe (openai) | none — indeterminate; UI shows spinner + elapsed |
| generating_notes | none — spinner + elapsed |

`stage_percent` stays `0` for indeterminate stages; the UI switches on stage name.

---

## 7. Canonical Transcript

```python
class Segment(BaseModel):
    id: int
    speaker: str            # "Speaker 1", "Speaker 2", ... (canonical, never renamed on disk)
    start: float            # seconds
    end: float
    text: str

class Transcript(BaseModel):
    meeting_id: str
    source_file: str
    duration_sec: float
    language: str           # auto-detected; "" if unknown
    provider: str           # "openai:gpt-4o-transcribe-diarize"
    created_at: datetime
    speakers: list[str]     # distinct labels present, in first-appearance order
    segments: list[Segment]
```

- `start`/`end` are best-effort; navigation anchors on `Segment.id`, never
  wall-clock.
- The OpenAI adapter maps `diarized_json` segments 1:1: each
  `{ speaker, start, end, text }` → `Segment` with a running `id`. `speakers` is
  derived. `language` from the response if present else `""`.

---

## 8. Notes

### 8.1 LLM output schema (`notes/schema.py`)

```python
class ActionItemOut(BaseModel):
    owner: str              # a speaker label present in the transcript, or "" if unclear
    task: str
    due: str | None         # ISO YYYY-MM-DD or null

class TopicOut(BaseModel):
    segment_id: int         # id of the segment where the topic starts
    topic: str

class NotesLLMOutput(BaseModel):
    summary: str
    action_items: list[ActionItemOut]
    decisions: list[str]
    topic_timeline: list[TopicOut]
    open_questions: list[str]
```

### 8.2 Generation (`notes/generate.py`)

- One call: `factory.chat_model().with_structured_output(NotesLLMOutput)`.
- Prompt includes: the full transcript rendered as `[<segment_id>] (mm:ss)
  <Speaker>: <text>` lines; the meeting date ("This meeting took place on
  <date>; resolve relative dates like 'next Friday' against it; if a due date is
  vague, use null and keep the phrase in the task text."); **"Write all notes in
  English regardless of the meeting's language."**
- Validate → if invalid, one corrective retry → else raise.
- Map `NotesLLMOutput` → `Notes` (adds `meeting_id`, `model`, `generated_at`).
- Record token usage into `usage.json` (§10).

```python
class Notes(BaseModel):
    meeting_id: str
    model: str
    generated_at: datetime
    summary: str
    action_items: list[ActionItem]     # same fields as ActionItemOut
    decisions: list[str]
    topic_timeline: list[Topic]        # segment_id, topic
    open_questions: list[str]
```

### 8.3 `notes.md` rendering (`notes/render.py`)

Fixed template, speaker labels substituted via `speaker_map` if present:

```markdown
# <meeting title = slug humanised> — <date>

_Model: <model> · generated <generated_at>_

## Summary
<summary>

## Action Items
- [ ] **<owner>** — <task> _(due <due>)_      # "(due —)" if null

## Decisions
- <decision>

## Topic Timeline
- `<mm:ss>` <topic>                            # mm:ss from segment start

## Open Questions
- <question>
```

---

## 9. Q&A

```python
class QATurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    asked_at: datetime
    usage: TokenUsage | None            # on assistant turns

# qa.json
class QALog(BaseModel):
    turns: list[QATurn]
    session_starts: list[int]           # indices into turns where a new session began
```

- On each question: build the **context bundle** (§11) → messages =
  `[system(with transcript + speaker names applied), *history_turns,
  user(question)]` → `chat_model().astream(...)` → tokens streamed into the chat
  pane.
- After completion: append user + assistant `QATurn`s to `qa.json`; add the
  assistant turn's token usage to `usage.json`.
- Prompt caching: `llm/caching.py` marks the transcript-bearing system block with
  `cache_control` when provider is `anthropic`; OpenAI/Azure cache automatically;
  no-op otherwise.
- Answers instructed to cite `Speaker Name @ mm:ss` as plain text where evidence
  exists.
- Answer language = the question's language (no instruction to translate).
- `Ctrl+L` clears the on-screen transcript of the chat and appends the new
  `len(turns)` to `session_starts`; history on disk is untouched and is still
  replayed into context.
- No length guard (v1 assumes ≤ ~2 h meetings).

---

## 10. Usage & Cost

```python
class TokenUsage(BaseModel):
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0

class UsageRecord(BaseModel):
    meeting_id: str
    transcription: dict          # { "minutes": float, "est_usd": float }
    notes: dict                  # { "usage": TokenUsage, "est_usd": float }
    qa: list[dict]               # [{ "usage": TokenUsage, "est_usd": float, "at": datetime }]

    def total_usd(self) -> float
```

- Transcription minutes = `transcript.duration_sec / 60`; `est_usd = minutes *
  price.per_min`.
- LLM `est_usd` from `pricing.py` using the model key
  `"<provider>:<model>"`; cached input billed at `cached_in_per_1m` when the
  provider reports cached tokens (`response.usage_metadata`).
- Missing price key → `est_usd = 0.0` and a one-time log warning.
- Displayed: `~$X.XX` in the meeting screen header (sum), and a transient
  `+~$0.0X` line after each chat answer.

---

## 11. Context Bundle

```python
class ContextBundle(BaseModel):
    transcript: Transcript
    speaker_map: SpeakerMap | None

    def transcript_text(self) -> str
        # "[<id>] (mm:ss) <mapped speaker>: <text>" lines
```

v1 constructs it from `{transcript, speaker_map}` only. V1.5 adds a
`visuals: list[VisualSegment] | None` field and interleaves visual lines by
timestamp. Nothing else in `notes/` or `qa/` changes.

---

## 12. Forward Compatibility — V1.5 (NOT built)

Visual understanding, **opt-in per meeting** via a checkbox in the
confirm-to-process modal (default OFF), stored in `job.json`. When on, a
`VisualStage` runs before `NotesStage`:

1. Keyframe extraction: ffmpeg scene-change filter + perceptual-hash dedup, drop
   low-text high-motion (camera) frames.
2. Per keyframe → **text**: OCR (Tesseract) + optional local caption model, or a
   hosted vision model. Never model-specific "visual tokens" — those are not
   portable across providers.
3. `visuals.json`: `[{ segment_id, timestamp, screen_text, description }]`.
4. `ContextBundle.visuals` populated; notes + Q&A prompts interleave visual lines
   by timestamp.

v1 guarantees that make this additive: source video retained; pipeline is an
ordered stage list; notes/Q&A consume a `ContextBundle`, not a bare transcript.

---

## 13. TUI

### 13.1 Screen stack

- **SetupWizard** (pushed on first run only): three steps — transcription
  provider, LLM provider + model, path confirmation — then writes `config.toml`,
  pops, and validates `.env` (missing → error screen with the list, quit).
- **MeetingList** (home): one row per meeting folder + one row per pending inbox
  file. Row shows: date, title, status badge, live percent/spinner, `~$total`.
  Keys: `enter` open, `n` (on a pending row) → ConfirmModal, `r` retry a
  failed/notes_failed row, `s` Settings, `q` quit.
- **ConfirmModal:** shows filename, detected duration, target `meeting_id`;
  `enter` enqueues, `esc` cancels. (V1.5: a "process video" checkbox.)
- **MeetingScreen:** `Tabs` = Transcript / Notes / Chat; header shows title,
  date, model, `~$total`. Keys: `1/2/3` or `tab` switch, `n` SpeakerModal,
  `e` export notes to `EXPORT_DIR`, `y` copy notes.md to clipboard, `esc` back.
- **TranscriptView:** turns (consecutive same-speaker segments merged), `mm:ss`
  prefix, mapped speaker header. Scrollable. `jump_to_segment(id)` scrolls + 1s
  highlight.
- **NotesView:** rendered sections; `topic_timeline` rows are focusable —
  `enter` switches to Transcript tab and calls `jump_to_segment`.
- **ChatView:** scrollback + input; streamed answers; `+~$` line; `Ctrl+L`
  clears view.
- **SpeakerModal:** one input per label in `transcript.speakers`, prefilled from
  `speaker_map.json`; `enter` saves `speaker_map.json`, `esc` cancels. Blank =
  keep `Speaker N`.
- **SettingsScreen:** same fields as the wizard; save rewrites `config.toml`;
  re-validates `.env`.

### 13.2 Inbox watching

- On launch: `MeetingStore.scan_inbox()` lists files in `INBOX_DIR` with a
  supported extension not already claimed → pending rows.
- While running: a `watchdog` observer posts an event to the app; the app waits
  until the file size is unchanged across two 1s polls, then adds a pending row.
- Supported extensions: `.mp4 .mkv .mov .webm .m4a .mp3 .wav .aac .flac .ogg`.
  Others are ignored (logged).
- On confirm: move the file into `DATA_DIR/{meeting_id}/source/`, write initial
  `job.json` (`status="queued"`), enqueue.

### 13.3 Logging

`logging_setup.configure(data_dir, debug)` — `RotatingFileHandler` on
`DATA_DIR/meetcap.log`, level INFO (DEBUG with `--debug`). Tracebacks on
exceptions. No stream handler (stdout is the UI).

---

## 14. Entry Point & Single Instance

`meetcap [FILE] [--debug]`

1. Parse args.
2. Load `config.toml` (or mark first-run).
3. `configure` logging.
4. Acquire `DATA_DIR/.lock`; if held by a live PID → print message, exit 1;
   stale → take it.
5. If first-run → the app pushes SetupWizard before MeetingList.
6. Validate `.env` for selected providers; missing → print list, exit 2.
7. If `FILE` given and readable → copy into `INBOX_DIR` first so it shows as a
   pending row.
8. Run `MeetcapApp`. Release lock on exit.

---

## 15. Testing

- **Unit (no network):**
  - `pipeline/runner` with `FakeTranscriber` + a fake chat model: status
    transitions, retry-from-missing-artifact, `failed` vs `notes_failed`,
    percent throttling.
  - `notes/schema` + `notes/generate`: valid parse; one corrective retry then
    raise; relative-date prompt content; English instruction present.
  - `notes/render`: `notes.md` output for a fixture `Notes`, incl. null `due`
    and `speaker_map` substitution.
  - `ids`: slug rules, collision suffixing.
  - `context_bundle`: `transcript_text()` line format with/without `speaker_map`.
  - `pricing` / `UsageRecord.total_usd`: estimates, cached-token billing, missing
    key → 0.
  - `config`: `.env` validation matrix per provider selection.
  - `storage/meeting_store`: folder round-trip, inbox scan, stale-lock takeover,
    file-move on confirm.
- **Adapter contract tests:**
  - `transcription/openai_diarize` against `fixtures/openai_diarized_response.json`
    (SDK mocked) → asserts canonical `Transcript`.
  - `llm/factory` + `notes/generate` against `fixtures/azure_notes_response.json`
    (chat model mocked) → asserts `Notes`.
- **TUI (`Pilot`):** launch (config present) → simulate a pending file → confirm
  → fake pipeline → row `ready` → open → tab through views → send a chat message
  (fake stream) → answer visible → open SpeakerModal, set a name, save → verify
  transcript view shows the name.
- **Smoke (`@pytest.mark.skipif` on missing keys):** `fixtures/sample_meeting.m4a`
  through the real `ExtractStage` + `TranscribeStage` + `NotesStage`; asserts a
  non-empty transcript and a schema-valid `Notes`.

Per `CLAUDE.md`: pytest runs as a Stop hook; a test file is exercised only once
its implementation module exists.
