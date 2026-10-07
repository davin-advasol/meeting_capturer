# Context: Meeting Capturer

A single-user, in-terminal (Textual TUI) app that turns one recorded meeting at a
time into a diarized transcript, structured notes, and a Q&A chat over the
transcript.

## Glossary

### Meeting
One recorded audio/video file and everything derived from it. Identified by
`meeting_id` = `YYYY-MM-DD-<filename-slug>` (`-2` suffix on collision) and stored
as one folder under `DATA_DIR`. The unit the user selects, processes, and opens.

Folder contents:

```
DATA_DIR/{meeting_id}/
  source/<original>      original file, moved in from the Inbox, kept forever
  audio.wav              ffmpeg-extracted, mono 16 kHz
  job.json              { status, stage, percent, error, timestamps }
  transcript.json        canonical diarized Transcript
  speaker_map.json      { "Speaker 1": "Priya", ... }  optional, editable
  notes.json             structured Notes — source of truth
  notes.md               Notes rendered to Markdown
  qa.json                append-only Q&A log with session markers
  usage.json             per-call token / minute / est-$ record
  visuals.json           (V1.5 only) per-keyframe screen_text + description
```

Write ordering is failure-resilient: `audio.wav` → `transcript.json`
(status `transcribed`) → `notes.json` + `notes.md` (status `ready`). A failure
during Notes still leaves a usable Transcript and working Chat.

### Inbox
A watched directory (`INBOX_DIR`). Recorded files dropped here appear in the
meeting list as **Pending** entries. Nothing in the Inbox is processed until the
user confirms (confirm-to-process — never zero-touch, because processing spends
API money).

### Pending
A meeting that has been noticed (in the Inbox) but not yet processed. Has a
source file but no transcript or notes. Becomes an ordinary Meeting once the user
confirms and the pipeline runs.

### Processing / the pipeline
The serial background job that turns a source file into a Meeting's artifacts:
extract audio → transcribe & diarize → (V1.5: visual pass) → generate notes →
store. Runs one job at a time on the TUI event loop; the meeting-list row shows
live stage/percent (real % for extract and local transcribe; spinner + elapsed
for cloud transcribe and Notes). UI stays usable meanwhile.

Job statuses: `pending` (Inbox, awaiting confirm) → `queued` → `extracting` /
`transcribing` / `generating_notes` → `ready`. Failure modes:
`notes_failed` (Transcript + Chat usable, Notes view shows error + retry) and
`failed` (died before a usable Transcript). A job is never left stuck. Transient
errors (429/5xx/timeout) auto-retry with backoff inside a stage; the Notes
schema-validation failure retries the LLM call once, then fails only that stage.
Retry resumes from the last good artifact.

### Transcript
The canonical, provider-agnostic diarized record of a Meeting: ordered segments,
each with speaker label, start/end time, and text. Every transcription provider's
output is normalized into this one shape.

### Notes
The structured summary of a Meeting produced by a single structured-output LLM
call over the full Transcript: summary, action items (owner/due), decisions,
topic timeline, open questions. `notes.json` is the source of truth; `notes.md`
is a rendering for export.

### Q&A / chat
A conversation over one Meeting's Transcript. Each question sends the entire
Transcript in context (no retrieval), plus the prior Q&A history for the Meeting
(multi-turn). Prompt caching keeps follow-ups cheap. Answers cite
`Speaker N @ mm:ss` as plain text.

### Context bundle
Whatever a Meeting's Notes and Q&A are given as source material. In v1 it
contains only the Transcript. Structured as a bundle (not "the transcript") so
V1.5 visual context is additive.

### Setup wizard
First-run flow (no `config.toml` present): choose transcription provider
(`openai` | `azure-openai`), choose LLM provider/model, then land on the meeting
list. Writes `config.toml`. Never writes secrets — API keys always live in
`.env`, which the app only validates (fail fast, listing what is missing).

### Settings
A TUI screen to change the provider choices the Setup wizard first captured.
Provider choices are global, not per-Meeting.

### Speaker / speaker map
Diarization labels speakers `Speaker 1`, `Speaker 2`, … The user optionally maps
these to real names in a post-transcription modal, stored as `speaker_map.json`
per Meeting and editable anytime. Canonical artifacts on disk always keep
`Speaker N`; names are substituted at read time — in the TUI, in the Q&A Context
bundle, and in the `notes.md` export.

### Usage
Per-Meeting record (`usage.json`) of what each provider call cost: transcription
minutes, Notes tokens (cache-read vs full split), and one entry per Q&A message.
Dollar figures are estimates from a price table in config, shown with a `~`.

## Views (TUI)

The three-view Meeting screen: **Transcript**, **Notes**, **Chat**. The home
screen is the **meeting list** (processed + Pending).

## Forward compatibility (not v1)

### V1.5 — visual understanding
Opt-in per Meeting via a toggle in the confirm-to-process dialog (default OFF).
When on: extract keyframes from the source video (scene-change detection +
perceptual-hash dedup, skip camera-only frames) → per frame produce **text**
(OCR + optional local caption model, or a hosted vision model) →
`visuals.json` of `{ segment_id, screen_text, description }` → merged into the
Context bundle by timestamp for Notes and Q&A.

Decoupled from the LLM layer: the intermediate is always text, never model-
specific visual tokens (those are not portable across providers). Transcription
never inspects the video track; visual regions come from a separate pass aligned
to the Transcript by timestamp.

v1 guarantees only: the source video is retained; the pipeline is an ordered
list of stages (a `visual` stage can slot in); Notes and Q&A consume a Context
bundle rather than a bare Transcript.
