# Meeting Capturer v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a web app that ingests one recorded meeting, produces a diarized transcript and structured notes, and answers questions over the transcript.

**Architecture:** A FastAPI backend runs a background pipeline (ffmpeg audio extraction → optional Silero VAD silence-trim → OpenAI `gpt-4o-transcribe-diarize` transcription → LangChain LLM structured-notes generation), storing each meeting as JSON/Markdown files under `DATA_DIR/{meeting_id}/`. A React (Vite + TypeScript) frontend uploads a file, polls job status, and renders notes, transcript, and a Q&A chat. Transcription and LLM providers sit behind swappable interfaces selected by config.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, pydantic / pydantic-settings, `openai` SDK (transcription), LangChain (`langchain-anthropic`, `langchain-openai`), `silero-vad`, ffmpeg (subprocess), pytest. Frontend: React 18, Vite, TypeScript, Vitest + Testing Library.

Reference spec: `docs/superpowers/specs/2026-06-15-meeting-capturer-v1-design.md`.

---

## File Structure

```
backend/
  pyproject.toml            # pytest config (pythonpath)
  requirements.txt          # runtime + dev deps
  .env.example              # config template
  app/
    __init__.py
    config.py               # Settings (pydantic-settings)
    models.py               # Segment, Transcript, TranscriptionResult, ActionItem,
                            #   TimelineEntry, Notes, StoredNotes, Job, JobStatus, QAEntry
    formatting.py           # seconds_to_mmss, format_transcript
    storage.py              # MeetingStorage (per-meeting folder IO)
    audio.py                # extract_audio, trim_silence, concat_speech
    transcription/
      __init__.py
      base.py               # Transcriber protocol
      openai_adapter.py     # OpenAITranscriber + _parse_diarized_response
      factory.py            # get_transcriber(settings)
    llm/
      __init__.py
      factory.py            # get_chat_model(settings)
    notes/
      __init__.py
      generator.py          # generate_notes(transcript, llm)
      renderer.py           # render_markdown(notes, title)
    qa/
      __init__.py
      answerer.py           # answer_question(transcript, question, history, llm)
    pipeline.py             # run_pipeline(...)
    main.py                 # FastAPI app + routes
  tests/
    conftest.py             # fixtures: tmp settings, fakes, sample audio
    test_models.py
    test_formatting.py
    test_storage.py
    test_audio.py
    test_transcription_openai.py
    test_transcription_factory.py
    test_llm_factory.py
    test_notes_generator.py
    test_notes_renderer.py
    test_qa.py
    test_pipeline.py
    test_api.py
    test_smoke.py

frontend/
  package.json, vite.config.ts, tsconfig.json, index.html
  src/
    types.ts                # mirrors backend models
    api.ts                  # typed fetch client
    App.tsx                 # top-level flow/state
    main.tsx
    components/
      UploadView.tsx
      ProgressView.tsx
      ResultsView.tsx
      NotesTab.tsx
      TranscriptTab.tsx
      QAChat.tsx
  tests/
    api.test.ts
    UploadView.test.tsx
```

**Responsibility boundaries:** `transcription/` only turns audio into segments; `notes/` only turns a transcript into notes + markdown; `qa/` only answers questions; `pipeline.py` orchestrates and owns job-status writes; `storage.py` is the only module that touches disk; `main.py` is thin HTTP glue. Each is testable in isolation with fakes.

---

## Conventions

- All backend commands run from `backend/`.
- Create and activate a virtualenv once: `python -m venv .venv && source .venv/Scripts/activate` (Windows Git Bash) before installing.
- Tests never hit the network or real APIs: transcription/LLM are replaced by fakes; ffmpeg/Silero calls are either monkeypatched or guarded behind an availability check.
- Commit after every task with the message shown.

---

## Task 1: Backend scaffold

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py` (empty)
- Create: `backend/app/config.py`
- Create: `backend/tests/__init__.py` (empty)
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: Create `backend/requirements.txt`**

```
fastapi==0.115.*
uvicorn[standard]==0.30.*
python-multipart==0.0.*
pydantic==2.*
pydantic-settings==2.*
openai==1.*
langchain==0.3.*
langchain-core==0.3.*
langchain-anthropic==0.3.*
langchain-openai==0.2.*
silero-vad==5.*
torch==2.*
pytest==8.*
httpx==0.27.*
```

- [ ] **Step 2: Create `backend/pyproject.toml`**

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
addopts = "-q"
```

- [ ] **Step 3: Create `backend/.env.example`**

```
DATA_DIR=./data
TRANSCRIBER_PROVIDER=openai
TRANSCRIBER_MODEL=gpt-4o-transcribe-diarize
OPENAI_API_KEY=
LLM_PROVIDER=anthropic
LLM_MODEL=claude-opus-4-8
ANTHROPIC_API_KEY=
ALLOWED_EXTENSIONS=.mp4,.mkv,.mov,.webm,.mp3,.m4a,.wav
VAD_MIN_SILENCE_SEC=1.5
```

- [ ] **Step 4: Create `backend/app/config.py`**

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    data_dir: str = "./data"
    transcriber_provider: str = "openai"
    transcriber_model: str = "gpt-4o-transcribe-diarize"
    openai_api_key: str | None = None
    llm_provider: str = "anthropic"
    llm_model: str = "claude-opus-4-8"
    anthropic_api_key: str | None = None
    allowed_extensions: str = ".mp4,.mkv,.mov,.webm,.mp3,.m4a,.wav"
    vad_min_silence_sec: float = 1.5

    def allowed_ext_set(self) -> set[str]:
        return {e.strip().lower() for e in self.allowed_extensions.split(",") if e.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 5: Create empty `backend/app/__init__.py` and `backend/tests/__init__.py`**

Both files are empty.

- [ ] **Step 6: Write `backend/tests/test_config.py`**

```python
from app.config import Settings


def test_allowed_ext_set_parses_and_normalizes():
    s = Settings(allowed_extensions=".MP4, .wav ,.mp3")
    assert s.allowed_ext_set() == {".mp4", ".wav", ".mp3"}


def test_defaults_present():
    s = Settings()
    assert s.transcriber_model == "gpt-4o-transcribe-diarize"
    assert s.llm_provider == "anthropic"
```

- [ ] **Step 7: Install deps and run the test**

Run: `cd backend && pip install -r requirements.txt && pytest tests/test_config.py -v`
Expected: 2 passed.

- [ ] **Step 8: Commit**

```bash
git add backend/
git commit -m "feat: backend scaffold and config"
```

---

## Task 2: Core data models

**Files:**
- Create: `backend/app/models.py`
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: Write the failing test `backend/tests/test_models.py`**

```python
from datetime import datetime

from app.models import (
    ActionItem, Job, JobStatus, Notes, Segment, StoredNotes,
    TimelineEntry, Transcript, TranscriptionResult, QAEntry,
)


def test_transcript_roundtrip():
    t = Transcript(
        meeting_id="m1", source_file="a.mp4", duration_sec=12.5,
        language="en", provider="openai:gpt-4o-transcribe-diarize",
        created_at=datetime(2026, 6, 15, 10, 0, 0), speakers=["Speaker 1"],
        segments=[Segment(id=0, speaker="Speaker 1", start=0.0, end=4.2, text="Hi")],
    )
    dumped = t.model_dump_json()
    again = Transcript.model_validate_json(dumped)
    assert again.segments[0].text == "Hi"


def test_notes_defaults_to_empty_lists():
    n = Notes(summary="s")
    assert n.action_items == [] and n.decisions == []
    assert n.topic_timeline == [] and n.open_questions == []


def test_stored_notes_extends_notes():
    sn = StoredNotes(
        summary="s", meeting_id="m1", model="claude-opus-4-8",
        generated_at=datetime(2026, 6, 15),
        action_items=[ActionItem(task="do x", owner="Speaker 1", due=None)],
        topic_timeline=[TimelineEntry(start=0.0, topic="Intro")],
    )
    assert sn.meeting_id == "m1"
    assert sn.action_items[0].owner == "Speaker 1"


def test_job_status_enum_and_defaults():
    j = Job(meeting_id="m1", source_file="a.mp4", vad_trim=True,
            created_at=datetime(2026, 6, 15), updated_at=datetime(2026, 6, 15))
    assert j.status == JobStatus.pending and j.percent == 0


def test_qa_entry():
    q = QAEntry(question="q?", answer="a.")
    assert q.citations == []
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models'`.

- [ ] **Step 3: Write `backend/app/models.py`**

```python
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Segment(BaseModel):
    id: int
    speaker: str
    start: float
    end: float
    text: str


class TranscriptionResult(BaseModel):
    """Provider output before meeting metadata is attached."""
    provider: str
    language: str | None = None
    segments: list[Segment]


class Transcript(BaseModel):
    meeting_id: str
    source_file: str
    duration_sec: float
    language: str | None = None
    provider: str
    created_at: datetime
    speakers: list[str]
    segments: list[Segment]


class ActionItem(BaseModel):
    task: str
    owner: str | None = None
    due: str | None = None


class TimelineEntry(BaseModel):
    start: float
    topic: str


class Notes(BaseModel):
    summary: str
    action_items: list[ActionItem] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    topic_timeline: list[TimelineEntry] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class StoredNotes(Notes):
    meeting_id: str
    model: str
    generated_at: datetime


class JobStatus(str, Enum):
    pending = "pending"
    extracting = "extracting"
    transcribing = "transcribing"
    transcribed = "transcribed"
    generating_notes = "generating_notes"
    done = "done"
    failed = "failed"


class Job(BaseModel):
    meeting_id: str
    source_file: str
    vad_trim: bool = False
    status: JobStatus = JobStatus.pending
    stage: str = "pending"
    percent: int = 0
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class QAEntry(BaseModel):
    question: str
    answer: str
    citations: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/tests/test_models.py
git commit -m "feat: core pydantic models"
```

---

## Task 3: Formatting utilities

**Files:**
- Create: `backend/app/formatting.py`
- Test: `backend/tests/test_formatting.py`

- [ ] **Step 1: Write the failing test `backend/tests/test_formatting.py`**

```python
from datetime import datetime

from app.formatting import seconds_to_mmss, format_transcript
from app.models import Segment, Transcript


def test_seconds_to_mmss():
    assert seconds_to_mmss(0) == "00:00"
    assert seconds_to_mmss(5) == "00:05"
    assert seconds_to_mmss(612.4) == "10:12"
    assert seconds_to_mmss(3661) == "61:01"


def _transcript():
    return Transcript(
        meeting_id="m1", source_file="a.mp4", duration_sec=20,
        provider="p", created_at=datetime(2026, 6, 15),
        speakers=["Speaker 1", "Speaker 2"],
        segments=[
            Segment(id=0, speaker="Speaker 1", start=0.0, end=4.0, text="Hello."),
            Segment(id=1, speaker="Speaker 2", start=4.5, end=9.0, text="Hi there."),
        ],
    )


def test_format_transcript_lines():
    text = format_transcript(_transcript())
    assert "[00:00] Speaker 1: Hello." in text
    assert "[00:04] Speaker 2: Hi there." in text
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_formatting.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.formatting'`.

- [ ] **Step 3: Write `backend/app/formatting.py`**

```python
from app.models import Transcript


def seconds_to_mmss(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 60:02d}:{total % 60:02d}"


def format_transcript(transcript: Transcript) -> str:
    lines = [
        f"[{seconds_to_mmss(seg.start)}] {seg.speaker}: {seg.text}"
        for seg in transcript.segments
    ]
    return "\n".join(lines)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_formatting.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/formatting.py backend/tests/test_formatting.py
git commit -m "feat: transcript formatting utilities"
```

---

## Task 4: Meeting storage

**Files:**
- Create: `backend/app/storage.py`
- Test: `backend/tests/test_storage.py`

`MeetingStorage` is the only module that touches the per-meeting folder. It writes/reads `job.json`, `transcript.json`, `notes.json`, `notes.md`, `qa.json`, and stores the uploaded source file.

- [ ] **Step 1: Write the failing test `backend/tests/test_storage.py`**

```python
from datetime import datetime

from app.models import (
    ActionItem, Job, JobStatus, QAEntry, Segment, StoredNotes, Transcript,
)
from app.storage import MeetingStorage


def test_create_meeting_writes_source_and_job(tmp_path):
    store = MeetingStorage(tmp_path)
    mid = store.create_meeting("weekly sync.mp4", b"\x00\x01\x02", vad_trim=True)
    assert (store.meeting_dir(mid) / "source" / "weekly sync.mp4").read_bytes() == b"\x00\x01\x02"
    job = store.load_job(mid)
    assert job.meeting_id == mid
    assert job.vad_trim is True
    assert job.status == JobStatus.pending
    assert job.source_file == "weekly sync.mp4"


def test_job_roundtrip(tmp_path):
    store = MeetingStorage(tmp_path)
    mid = store.create_meeting("a.mp4", b"x", vad_trim=False)
    job = store.load_job(mid)
    job.status = JobStatus.transcribing
    job.percent = 30
    store.save_job(job)
    assert store.load_job(mid).percent == 30


def test_transcript_roundtrip(tmp_path):
    store = MeetingStorage(tmp_path)
    mid = store.create_meeting("a.mp4", b"x", vad_trim=False)
    t = Transcript(
        meeting_id=mid, source_file="a.mp4", duration_sec=10, provider="p",
        created_at=datetime(2026, 6, 15), speakers=["Speaker 1"],
        segments=[Segment(id=0, speaker="Speaker 1", start=0, end=1, text="hi")],
    )
    store.save_transcript(t)
    assert store.load_transcript(mid).segments[0].text == "hi"


def test_notes_and_markdown(tmp_path):
    store = MeetingStorage(tmp_path)
    mid = store.create_meeting("a.mp4", b"x", vad_trim=False)
    sn = StoredNotes(
        summary="s", meeting_id=mid, model="claude-opus-4-8",
        generated_at=datetime(2026, 6, 15),
        action_items=[ActionItem(task="do x")],
    )
    store.save_notes(sn)
    store.save_notes_markdown(mid, "# Notes\n")
    assert store.load_notes(mid).summary == "s"
    assert store.load_notes_markdown(mid) == "# Notes\n"


def test_qa_append(tmp_path):
    store = MeetingStorage(tmp_path)
    mid = store.create_meeting("a.mp4", b"x", vad_trim=False)
    assert store.load_qa(mid) == []
    store.append_qa(mid, QAEntry(question="q1", answer="a1"))
    store.append_qa(mid, QAEntry(question="q2", answer="a2"))
    qa = store.load_qa(mid)
    assert [e.question for e in qa] == ["q1", "q2"]


def test_exists(tmp_path):
    store = MeetingStorage(tmp_path)
    assert store.exists("nope") is False
    mid = store.create_meeting("a.mp4", b"x", vad_trim=False)
    assert store.exists(mid) is True
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_storage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.storage'`.

- [ ] **Step 3: Write `backend/app/storage.py`**

```python
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.models import Job, JobStatus, QAEntry, StoredNotes, Transcript


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MeetingStorage:
    def __init__(self, data_dir: str | Path):
        self.root = Path(data_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    # --- paths ---
    def meeting_dir(self, meeting_id: str) -> Path:
        return self.root / meeting_id

    def source_path(self, meeting_id: str) -> Path:
        job = self.load_job(meeting_id)
        return self.meeting_dir(meeting_id) / "source" / job.source_file

    def audio_path(self, meeting_id: str) -> Path:
        return self.meeting_dir(meeting_id) / "audio.wav"

    def exists(self, meeting_id: str) -> bool:
        return (self.meeting_dir(meeting_id) / "job.json").exists()

    # --- lifecycle ---
    def create_meeting(self, source_filename: str, file_bytes: bytes, vad_trim: bool) -> str:
        meeting_id = uuid.uuid4().hex[:12]
        mdir = self.meeting_dir(meeting_id)
        (mdir / "source").mkdir(parents=True, exist_ok=True)
        (mdir / "source" / source_filename).write_bytes(file_bytes)
        now = _now()
        job = Job(
            meeting_id=meeting_id, source_file=source_filename, vad_trim=vad_trim,
            status=JobStatus.pending, stage="pending", percent=0,
            created_at=now, updated_at=now,
        )
        self.save_job(job)
        return meeting_id

    # --- job ---
    def save_job(self, job: Job) -> None:
        job.updated_at = _now()
        (self.meeting_dir(job.meeting_id) / "job.json").write_text(
            job.model_dump_json(indent=2), encoding="utf-8"
        )

    def load_job(self, meeting_id: str) -> Job:
        raw = (self.meeting_dir(meeting_id) / "job.json").read_text(encoding="utf-8")
        return Job.model_validate_json(raw)

    # --- transcript ---
    def save_transcript(self, transcript: Transcript) -> None:
        (self.meeting_dir(transcript.meeting_id) / "transcript.json").write_text(
            transcript.model_dump_json(indent=2), encoding="utf-8"
        )

    def load_transcript(self, meeting_id: str) -> Transcript:
        raw = (self.meeting_dir(meeting_id) / "transcript.json").read_text(encoding="utf-8")
        return Transcript.model_validate_json(raw)

    # --- notes ---
    def save_notes(self, notes: StoredNotes) -> None:
        (self.meeting_dir(notes.meeting_id) / "notes.json").write_text(
            notes.model_dump_json(indent=2), encoding="utf-8"
        )

    def load_notes(self, meeting_id: str) -> StoredNotes:
        raw = (self.meeting_dir(meeting_id) / "notes.json").read_text(encoding="utf-8")
        return StoredNotes.model_validate_json(raw)

    def save_notes_markdown(self, meeting_id: str, markdown: str) -> None:
        (self.meeting_dir(meeting_id) / "notes.md").write_text(markdown, encoding="utf-8")

    def load_notes_markdown(self, meeting_id: str) -> str:
        return (self.meeting_dir(meeting_id) / "notes.md").read_text(encoding="utf-8")

    # --- qa ---
    def load_qa(self, meeting_id: str) -> list[QAEntry]:
        path = self.meeting_dir(meeting_id) / "qa.json"
        if not path.exists():
            return []
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
        return [QAEntry.model_validate(e) for e in data]

    def append_qa(self, meeting_id: str, entry: QAEntry) -> None:
        import json
        entries = self.load_qa(meeting_id)
        entries.append(entry)
        path = self.meeting_dir(meeting_id) / "qa.json"
        path.write_text(
            json.dumps([e.model_dump() for e in entries], indent=2), encoding="utf-8"
        )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_storage.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/storage.py backend/tests/test_storage.py
git commit -m "feat: per-meeting file storage"
```

---

## Task 5: Silence concatenation (pure function)

**Files:**
- Create: `backend/app/audio.py` (partial — `concat_speech` only)
- Test: `backend/tests/test_audio.py` (partial)

We isolate the pure list-math of stitching speech regions so it is testable without the Silero model or audio files.

- [ ] **Step 1: Write the failing test `backend/tests/test_audio.py`**

```python
from app.audio import concat_speech


def test_concat_speech_keeps_only_speech_regions():
    samples = list(range(20))  # 0..19
    # keep [2,5) and [10,13)
    timestamps = [{"start": 2, "end": 5}, {"start": 10, "end": 13}]
    assert concat_speech(samples, timestamps) == [2, 3, 4, 10, 11, 12]


def test_concat_speech_empty_returns_all():
    samples = [9, 8, 7]
    assert concat_speech(samples, []) == [9, 8, 7]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_audio.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.audio'`.

- [ ] **Step 3: Create `backend/app/audio.py` with `concat_speech`**

```python
from typing import Sequence


def concat_speech(samples: Sequence, timestamps: list[dict]) -> list:
    """Keep only the [start, end) sample ranges flagged as speech.

    `timestamps` is Silero's output (sample indices). Empty list = keep all.
    """
    if not timestamps:
        return list(samples)
    kept: list = []
    for ts in timestamps:
        kept.extend(samples[ts["start"]:ts["end"]])
    return kept
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_audio.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/audio.py backend/tests/test_audio.py
git commit -m "feat: concat_speech pure helper"
```

---

## Task 6: Audio extraction and VAD trim

**Files:**
- Modify: `backend/app/audio.py`
- Test: `backend/tests/test_audio.py` (add ffmpeg-guarded cases)

`extract_audio` shells out to ffmpeg (mono 16 kHz WAV) and reads duration via ffprobe. `trim_silence` uses Silero to find speech and rewrites the WAV. Audio tests are guarded so the suite passes on machines without ffmpeg.

- [ ] **Step 1: Add ffmpeg-guarded tests to `backend/tests/test_audio.py`**

```python
import shutil
import subprocess
import wave

import pytest

from app.audio import extract_audio

ffmpeg_available = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
requires_ffmpeg = pytest.mark.skipif(not ffmpeg_available, reason="ffmpeg/ffprobe not installed")


@requires_ffmpeg
def test_extract_audio_produces_mono_16k_wav(tmp_path):
    src = tmp_path / "tone.wav"
    # 2-second 440 Hz stereo 44.1k tone via ffmpeg
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-ac", "2", "-ar", "44100", str(src)],
        check=True, capture_output=True,
    )
    dest = tmp_path / "audio.wav"
    duration = extract_audio(src, dest)
    assert dest.exists()
    with wave.open(str(dest), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getframerate() == 16000
    assert 1.8 <= duration <= 2.2
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_audio.py -v`
Expected: FAIL with `ImportError: cannot import name 'extract_audio'` (or the ffmpeg test is skipped — if skipped, temporarily un-skip locally by ensuring ffmpeg is installed; ffmpeg is a project prerequisite).

- [ ] **Step 3: Add `extract_audio` and `trim_silence` to `backend/app/audio.py`**

```python
import json
import subprocess
from pathlib import Path


def extract_audio(source: Path, dest: Path) -> float:
    """Extract mono 16 kHz WAV from any audio/video source. Returns duration (s)."""
    source, dest = Path(source), Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000", str(dest)],
        check=True, capture_output=True,
    )
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(dest)],
        check=True, capture_output=True, text=True,
    )
    return float(json.loads(probe.stdout)["format"]["duration"])


def trim_silence(audio: Path, dest: Path, min_silence_sec: float = 1.5) -> None:
    """Remove long silences from a 16 kHz mono WAV using Silero VAD."""
    import torch
    from silero_vad import get_speech_timestamps, load_silero_vad, read_audio, save_audio

    audio, dest = Path(audio), Path(dest)
    model = load_silero_vad()
    wav = read_audio(str(audio), sampling_rate=16000)
    timestamps = get_speech_timestamps(
        wav, model, sampling_rate=16000,
        min_silence_duration_ms=int(min_silence_sec * 1000),
    )
    kept = concat_speech(wav, timestamps)
    speech = torch.stack(list(kept)) if (timestamps and len(kept) > 0) else wav
    save_audio(str(dest), speech, sampling_rate=16000)
```

> Note: `wav` is a 1-D torch tensor; `concat_speech` slicing works element-wise and returns a list of 0-dim tensors, hence `torch.stack`. If `kept` is empty or no silence found, fall back to the original `wav`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_audio.py -v`
Expected: 3 passed (the 2 pure tests + the ffmpeg extract test). If ffmpeg is absent the extract test is skipped — install ffmpeg before continuing.

- [ ] **Step 5: Commit**

```bash
git add backend/app/audio.py backend/tests/test_audio.py
git commit -m "feat: ffmpeg audio extraction and Silero VAD trim"
```

---

## Task 7: OpenAI transcription adapter

**Files:**
- Create: `backend/app/transcription/__init__.py` (empty)
- Create: `backend/app/transcription/base.py`
- Create: `backend/app/transcription/openai_adapter.py`
- Test: `backend/tests/test_transcription_openai.py`

The adapter normalizes OpenAI's `diarized_json` response into `TranscriptionResult`. We factor a pure `_parse_diarized_response(data)` so parsing is tested without the network.

- [ ] **Step 1: Write the failing test `backend/tests/test_transcription_openai.py`**

```python
from app.transcription.openai_adapter import _parse_diarized_response


def test_parse_diarized_response_builds_segments():
    data = {
        "segments": [
            {"speaker": "Speaker 1", "start": 0.0, "end": 4.2, "text": "Hi"},
            {"speaker": "Speaker 2", "start": 4.5, "end": 9.8, "text": "Hello"},
        ]
    }
    segments = _parse_diarized_response(data)
    assert [s.id for s in segments] == [0, 1]
    assert segments[1].speaker == "Speaker 2"
    assert segments[0].text == "Hi"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_transcription_openai.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.transcription'`.

- [ ] **Step 3: Create `backend/app/transcription/__init__.py` (empty) and `backend/app/transcription/base.py`**

```python
from pathlib import Path
from typing import Protocol

from app.models import TranscriptionResult


class Transcriber(Protocol):
    name: str

    def transcribe(self, audio_path: Path, language: str | None = None) -> TranscriptionResult:
        ...
```

- [ ] **Step 4: Create `backend/app/transcription/openai_adapter.py`**

```python
from pathlib import Path

from app.models import Segment, TranscriptionResult


def _parse_diarized_response(data: dict) -> list[Segment]:
    segments = []
    for i, seg in enumerate(data.get("segments", [])):
        segments.append(Segment(
            id=i,
            speaker=seg["speaker"],
            start=float(seg["start"]),
            end=float(seg["end"]),
            text=seg["text"],
        ))
    return segments


class OpenAITranscriber:
    name = "openai:gpt-4o-transcribe-diarize"

    def __init__(self, api_key: str, model: str = "gpt-4o-transcribe-diarize"):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key)
        self._model = model
        self.name = f"openai:{model}"

    def transcribe(self, audio_path: Path, language: str | None = None) -> TranscriptionResult:
        with open(audio_path, "rb") as f:
            resp = self._client.audio.transcriptions.create(
                model=self._model,
                file=f,
                response_format="diarized_json",
                chunking_strategy="auto",
                **({"language": language} if language else {}),
            )
        # SDK returns an object; normalize to dict for the pure parser.
        data = resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)
        segments = _parse_diarized_response(data)
        return TranscriptionResult(provider=self.name, language=language, segments=segments)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/test_transcription_openai.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/transcription/ backend/tests/test_transcription_openai.py
git commit -m "feat: OpenAI diarized transcription adapter"
```

---

## Task 8: Transcriber factory

**Files:**
- Create: `backend/app/transcription/factory.py`
- Test: `backend/tests/test_transcription_factory.py`

- [ ] **Step 1: Write the failing test `backend/tests/test_transcription_factory.py`**

```python
import pytest

from app.config import Settings
from app.transcription.factory import get_transcriber


def test_get_transcriber_openai():
    settings = Settings(transcriber_provider="openai", openai_api_key="sk-test")
    t = get_transcriber(settings)
    assert t.name.startswith("openai:")


def test_get_transcriber_missing_key_raises():
    settings = Settings(transcriber_provider="openai", openai_api_key=None)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        get_transcriber(settings)


def test_get_transcriber_unknown_provider_raises():
    settings = Settings(transcriber_provider="bogus")
    with pytest.raises(ValueError, match="Unknown transcriber provider"):
        get_transcriber(settings)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_transcription_factory.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `backend/app/transcription/factory.py`**

```python
from app.config import Settings
from app.transcription.base import Transcriber


def get_transcriber(settings: Settings) -> Transcriber:
    provider = settings.transcriber_provider.lower()
    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for the openai transcriber")
        from app.transcription.openai_adapter import OpenAITranscriber
        return OpenAITranscriber(
            api_key=settings.openai_api_key, model=settings.transcriber_model
        )
    raise ValueError(f"Unknown transcriber provider: {settings.transcriber_provider}")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_transcription_factory.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/transcription/factory.py backend/tests/test_transcription_factory.py
git commit -m "feat: transcriber factory with config validation"
```

---

## Task 9: LLM factory

**Files:**
- Create: `backend/app/llm/__init__.py` (empty)
- Create: `backend/app/llm/factory.py`
- Test: `backend/tests/test_llm_factory.py`

- [ ] **Step 1: Write the failing test `backend/tests/test_llm_factory.py`**

```python
import pytest

from app.config import Settings
from app.llm.factory import get_chat_model


def test_unknown_provider_raises():
    settings = Settings(llm_provider="bogus")
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_chat_model(settings)


def test_anthropic_missing_key_raises():
    settings = Settings(llm_provider="anthropic", anthropic_api_key=None)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        get_chat_model(settings)


def test_openai_missing_key_raises():
    settings = Settings(llm_provider="openai", openai_api_key=None)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        get_chat_model(settings)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_llm_factory.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `backend/app/llm/__init__.py` (empty) and `backend/app/llm/factory.py`**

```python
from app.config import Settings


def get_chat_model(settings: Settings):
    """Return a LangChain chat model selected by config."""
    provider = settings.llm_provider.lower()
    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for the anthropic provider")
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=settings.llm_model, api_key=settings.anthropic_api_key)
    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for the openai provider")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=settings.llm_model, api_key=settings.openai_api_key)
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_llm_factory.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm/ backend/tests/test_llm_factory.py
git commit -m "feat: LangChain LLM factory with config validation"
```

---

## Task 10: Notes generator

**Files:**
- Create: `backend/app/notes/__init__.py` (empty)
- Create: `backend/app/notes/generator.py`
- Test: `backend/tests/test_notes_generator.py`

`generate_notes` formats the transcript, calls the LLM's structured-output mode, and returns a `Notes`. We test orchestration with a fake LLM exposing `.with_structured_output(schema).invoke(messages)`.

- [ ] **Step 1: Write the failing test `backend/tests/test_notes_generator.py`**

```python
from datetime import datetime

from app.models import ActionItem, Notes, Segment, TimelineEntry, Transcript
from app.notes.generator import generate_notes


class _FakeStructured:
    def __init__(self, result, captured):
        self._result = result
        self._captured = captured

    def invoke(self, messages):
        self._captured["messages"] = messages
        return self._result


class FakeLLM:
    def __init__(self, result):
        self._result = result
        self.captured = {}

    def with_structured_output(self, schema):
        assert schema is Notes
        return _FakeStructured(self._result, self.captured)


def _transcript():
    return Transcript(
        meeting_id="m1", source_file="a.mp4", duration_sec=20, provider="p",
        created_at=datetime(2026, 6, 15), speakers=["Speaker 1"],
        segments=[Segment(id=0, speaker="Speaker 1", start=0, end=4, text="We ship Friday.")],
    )


def test_generate_notes_returns_model_and_sends_transcript():
    expected = Notes(
        summary="We agreed to ship Friday.",
        action_items=[ActionItem(task="Ship", owner="Speaker 1", due="2026-06-19")],
        topic_timeline=[TimelineEntry(start=0.0, topic="Release")],
    )
    llm = FakeLLM(expected)
    notes = generate_notes(_transcript(), llm)
    assert notes.summary == "We agreed to ship Friday."
    # the transcript text reached the model
    sent = "".join(str(m) for m in llm.captured["messages"])
    assert "We ship Friday." in sent
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_notes_generator.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `backend/app/notes/__init__.py` (empty) and `backend/app/notes/generator.py`**

```python
from langchain_core.messages import HumanMessage, SystemMessage

from app.formatting import format_transcript
from app.models import Notes, Transcript

NOTES_SYSTEM_PROMPT = (
    "You are a meeting analyst. Given a diarized meeting transcript, produce structured "
    "notes. Use the speaker labels exactly as they appear when attributing action items. "
    "Sections:\n"
    "- summary: a concise prose overview of the meeting.\n"
    "- action_items: concrete tasks; set owner to the speaker label responsible (or null), "
    "and due to any date mentioned (ISO yyyy-mm-dd) or null.\n"
    "- decisions: explicit decisions reached.\n"
    "- topic_timeline: topics in order; set start to the approximate start time in seconds "
    "taken from the [mm:ss] markers.\n"
    "- open_questions: unresolved questions or problems raised.\n"
    "Only include items genuinely supported by the transcript."
)


def generate_notes(transcript: Transcript, llm) -> Notes:
    structured = llm.with_structured_output(Notes)
    transcript_text = format_transcript(transcript)
    return structured.invoke([
        SystemMessage(content=NOTES_SYSTEM_PROMPT),
        HumanMessage(content=f"Meeting transcript:\n\n{transcript_text}"),
    ])
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_notes_generator.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/notes/__init__.py backend/app/notes/generator.py backend/tests/test_notes_generator.py
git commit -m "feat: structured notes generation"
```

---

## Task 11: Notes Markdown renderer

**Files:**
- Create: `backend/app/notes/renderer.py`
- Test: `backend/tests/test_notes_renderer.py`

- [ ] **Step 1: Write the failing test `backend/tests/test_notes_renderer.py`**

```python
from app.models import ActionItem, Notes, TimelineEntry
from app.notes.renderer import render_markdown


def test_render_markdown_has_all_sections():
    notes = Notes(
        summary="The team reviewed the rollout.",
        action_items=[
            ActionItem(task="Ship auth fix", owner="Speaker 2", due="2026-06-18"),
            ActionItem(task="Draft comms", owner=None, due=None),
        ],
        decisions=["Delay billing migration to Q4"],
        topic_timeline=[TimelineEntry(start=612.4, topic="Billing risks")],
        open_questions=["Who owns the backfill?"],
    )
    md = render_markdown(notes, title="Weekly Sync")

    assert md.startswith("# Weekly Sync — Notes")
    assert "## Summary" in md
    assert "The team reviewed the rollout." in md
    assert "- [ ] **Speaker 2** — Ship auth fix (due 2026-06-18)" in md
    assert "- [ ] Draft comms" in md
    assert "## Decisions" in md
    assert "- Delay billing migration to Q4" in md
    assert "## Topic Timeline" in md
    assert "- [10:12] Billing risks" in md
    assert "## Open Questions" in md
    assert "- Who owns the backfill?" in md


def test_render_markdown_omits_empty_sections():
    md = render_markdown(Notes(summary="Just a summary."), title="X")
    assert "## Action Items" not in md
    assert "## Summary" in md
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_notes_renderer.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `backend/app/notes/renderer.py`**

```python
from app.formatting import seconds_to_mmss
from app.models import Notes


def render_markdown(notes: Notes, title: str) -> str:
    parts: list[str] = [f"# {title} — Notes", ""]

    parts += ["## Summary", "", notes.summary, ""]

    if notes.action_items:
        parts += ["## Action Items", ""]
        for item in notes.action_items:
            owner = f"**{item.owner}** — " if item.owner else ""
            due = f" (due {item.due})" if item.due else ""
            parts.append(f"- [ ] {owner}{item.task}{due}")
        parts.append("")

    if notes.decisions:
        parts += ["## Decisions", ""]
        parts += [f"- {d}" for d in notes.decisions]
        parts.append("")

    if notes.topic_timeline:
        parts += ["## Topic Timeline", ""]
        parts += [f"- [{seconds_to_mmss(t.start)}] {t.topic}" for t in notes.topic_timeline]
        parts.append("")

    if notes.open_questions:
        parts += ["## Open Questions", ""]
        parts += [f"- {q}" for q in notes.open_questions]
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_notes_renderer.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/notes/renderer.py backend/tests/test_notes_renderer.py
git commit -m "feat: notes Markdown renderer"
```

---

## Task 12: Q&A answerer

**Files:**
- Create: `backend/app/qa/__init__.py` (empty)
- Create: `backend/app/qa/answerer.py`
- Test: `backend/tests/test_qa.py`

`answer_question` sends the full transcript plus prior Q&A history and the new question to the LLM, returning a `QAEntry`. Tested with a fake chat model returning an `AIMessage`-like object.

- [ ] **Step 1: Write the failing test `backend/tests/test_qa.py`**

```python
from datetime import datetime

from app.models import QAEntry, Segment, Transcript
from app.qa.answerer import answer_question


class _Resp:
    def __init__(self, content):
        self.content = content


class FakeChat:
    def __init__(self, answer):
        self._answer = answer
        self.captured = {}

    def invoke(self, messages):
        self.captured["messages"] = messages
        return _Resp(self._answer)


def _transcript():
    return Transcript(
        meeting_id="m1", source_file="a.mp4", duration_sec=20, provider="p",
        created_at=datetime(2026, 6, 15), speakers=["Speaker 1"],
        segments=[Segment(id=0, speaker="Speaker 1", start=0, end=4, text="Budget is approved.")],
    )


def test_answer_question_returns_entry_with_transcript_context():
    chat = FakeChat("Yes, the budget was approved.")
    entry = answer_question(_transcript(), "Was the budget approved?", [], chat)
    assert isinstance(entry, QAEntry)
    assert entry.question == "Was the budget approved?"
    assert entry.answer == "Yes, the budget was approved."
    sent = "".join(str(m) for m in chat.captured["messages"])
    assert "Budget is approved." in sent


def test_answer_question_includes_history():
    chat = FakeChat("Follow-up answer.")
    history = [QAEntry(question="Q1?", answer="A1.")]
    answer_question(_transcript(), "Q2?", history, chat)
    sent = "".join(str(m) for m in chat.captured["messages"])
    assert "Q1?" in sent and "A1." in sent
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_qa.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `backend/app/qa/__init__.py` (empty) and `backend/app/qa/answerer.py`**

```python
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.formatting import format_transcript
from app.models import QAEntry, Transcript

QA_SYSTEM_PROMPT = (
    "You answer questions about a single meeting using only the transcript provided. "
    "If the answer is not in the transcript, say so. When helpful, cite the speaker and "
    "approximate time (the [mm:ss] markers) inline in your answer."
)


def answer_question(
    transcript: Transcript,
    question: str,
    history: list[QAEntry],
    llm,
) -> QAEntry:
    transcript_text = format_transcript(transcript)
    messages = [
        SystemMessage(content=QA_SYSTEM_PROMPT),
        HumanMessage(content=f"Meeting transcript:\n\n{transcript_text}"),
    ]
    for past in history:
        messages.append(HumanMessage(content=past.question))
        messages.append(AIMessage(content=past.answer))
    messages.append(HumanMessage(content=question))

    response = llm.invoke(messages)
    answer = response.content if hasattr(response, "content") else str(response)
    return QAEntry(question=question, answer=answer, citations=[])
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_qa.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/qa/ backend/tests/test_qa.py
git commit -m "feat: transcript Q&A answerer"
```

---

## Task 13: Pipeline orchestration

**Files:**
- Create: `backend/app/pipeline.py`
- Test: `backend/tests/test_pipeline.py`

`run_pipeline` drives the stages, writing job status after each, and is failure-safe (any exception marks the job `failed` with the message). Tests use fakes for the transcriber and LLM and monkeypatch the ffmpeg/Silero functions so no media or network is touched.

- [ ] **Step 1: Write the failing test `backend/tests/test_pipeline.py`**

```python
from datetime import datetime

import app.pipeline as pipeline_mod
from app.models import (
    JobStatus, Notes, Segment, TranscriptionResult,
)
from app.pipeline import run_pipeline
from app.storage import MeetingStorage


class FakeTranscriber:
    name = "fake"

    def transcribe(self, audio_path, language=None):
        return TranscriptionResult(
            provider="fake", language="en",
            segments=[
                Segment(id=0, speaker="Speaker 1", start=0, end=4, text="Hello."),
                Segment(id=1, speaker="Speaker 2", start=4, end=8, text="We ship Friday."),
            ],
        )


class _Structured:
    def invoke(self, messages):
        return Notes(summary="Shipping Friday.")


class FakeLLM:
    def with_structured_output(self, schema):
        return _Structured()


def _setup(tmp_path, monkeypatch, vad=False):
    store = MeetingStorage(tmp_path)
    mid = store.create_meeting("a.mp4", b"data", vad_trim=vad)
    monkeypatch.setattr(pipeline_mod, "extract_audio", lambda src, dest: 8.0)
    trims = {}
    monkeypatch.setattr(
        pipeline_mod, "trim_silence",
        lambda audio, dest, min_silence_sec: trims.setdefault("called", True),
    )
    return store, mid, trims


def test_pipeline_happy_path(tmp_path, monkeypatch):
    store, mid, _ = _setup(tmp_path, monkeypatch)
    run_pipeline(mid, store, FakeTranscriber(), FakeLLM(), "claude-x", vad_trim=False)

    job = store.load_job(mid)
    assert job.status == JobStatus.done and job.percent == 100
    transcript = store.load_transcript(mid)
    assert transcript.duration_sec == 8.0
    assert transcript.speakers == ["Speaker 1", "Speaker 2"]
    notes = store.load_notes(mid)
    assert notes.summary == "Shipping Friday."
    assert notes.model == "claude-x"
    assert "# a.mp4 — Notes" in store.load_notes_markdown(mid)


def test_pipeline_runs_vad_when_enabled(tmp_path, monkeypatch):
    store, mid, trims = _setup(tmp_path, monkeypatch, vad=True)
    run_pipeline(mid, store, FakeTranscriber(), FakeLLM(), "claude-x", vad_trim=True)
    assert trims.get("called") is True


def test_pipeline_marks_failed_on_error(tmp_path, monkeypatch):
    store, mid, _ = _setup(tmp_path, monkeypatch)

    class Boom:
        name = "boom"

        def transcribe(self, audio_path, language=None):
            raise RuntimeError("provider down")

    run_pipeline(mid, store, Boom(), FakeLLM(), "claude-x", vad_trim=False)
    job = store.load_job(mid)
    assert job.status == JobStatus.failed
    assert "provider down" in job.error
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.pipeline'`.

- [ ] **Step 3: Write `backend/app/pipeline.py`**

```python
from datetime import datetime, timezone

from app.audio import extract_audio, trim_silence
from app.models import JobStatus, StoredNotes, Transcript
from app.notes.generator import generate_notes
from app.notes.renderer import render_markdown
from app.storage import MeetingStorage


def _set_stage(store: MeetingStorage, meeting_id: str, status: JobStatus, percent: int):
    job = store.load_job(meeting_id)
    job.status = status
    job.stage = status.value
    job.percent = percent
    store.save_job(job)


def run_pipeline(
    meeting_id: str,
    store: MeetingStorage,
    transcriber,
    llm,
    llm_model: str,
    vad_trim: bool,
    vad_min_silence_sec: float = 1.5,
) -> None:
    try:
        job = store.load_job(meeting_id)
        source = store.source_path(meeting_id)
        audio = store.audio_path(meeting_id)

        _set_stage(store, meeting_id, JobStatus.extracting, 10)
        duration = extract_audio(source, audio)
        if vad_trim:
            trim_silence(audio, audio, min_silence_sec=vad_min_silence_sec)

        _set_stage(store, meeting_id, JobStatus.transcribing, 30)
        result = transcriber.transcribe(audio)
        speakers = list(dict.fromkeys(s.speaker for s in result.segments))
        transcript = Transcript(
            meeting_id=meeting_id,
            source_file=job.source_file,
            duration_sec=duration,
            language=result.language,
            provider=result.provider,
            created_at=datetime.now(timezone.utc),
            speakers=speakers,
            segments=result.segments,
        )
        store.save_transcript(transcript)
        _set_stage(store, meeting_id, JobStatus.transcribed, 70)

        _set_stage(store, meeting_id, JobStatus.generating_notes, 80)
        notes = generate_notes(transcript, llm)
        stored = StoredNotes(
            **notes.model_dump(),
            meeting_id=meeting_id,
            model=llm_model,
            generated_at=datetime.now(timezone.utc),
        )
        store.save_notes(stored)
        store.save_notes_markdown(meeting_id, render_markdown(notes, title=job.source_file))

        _set_stage(store, meeting_id, JobStatus.done, 100)
    except Exception as exc:  # noqa: BLE001 - we surface any failure on the job
        job = store.load_job(meeting_id)
        job.status = JobStatus.failed
        job.stage = "failed"
        job.error = str(exc)
        store.save_job(job)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_pipeline.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline.py backend/tests/test_pipeline.py
git commit -m "feat: meeting processing pipeline"
```

---

## Task 14: FastAPI app — upload and dependency wiring

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_api.py` (upload cases)

The app builds providers once at startup from settings and exposes them on `app.state`. Upload validates extension, stores the file, and schedules the pipeline as a FastAPI background task.

- [ ] **Step 1: Write `backend/tests/conftest.py`**

```python
import pytest

from app.config import Settings
from app.models import Notes, Segment, TranscriptionResult


class FakeTranscriber:
    name = "fake"

    def transcribe(self, audio_path, language=None):
        return TranscriptionResult(
            provider="fake", language="en",
            segments=[Segment(id=0, speaker="Speaker 1", start=0, end=4, text="Hello.")],
        )


class _Structured:
    def invoke(self, messages):
        return Notes(summary="A summary.")


class FakeLLM:
    def with_structured_output(self, schema):
        return _Structured()

    def invoke(self, messages):
        class _R:
            content = "A fake answer."
        return _R()


@pytest.fixture
def test_settings(tmp_path):
    return Settings(
        data_dir=str(tmp_path / "data"),
        transcriber_provider="openai", openai_api_key="sk-test",
        llm_provider="anthropic", anthropic_api_key="sk-ant",
        llm_model="claude-test",
    )
```

- [ ] **Step 2: Write the failing test `backend/tests/test_api.py` (upload cases)**

```python
import app.pipeline as pipeline_mod
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import FakeLLM, FakeTranscriber


def _client(test_settings, monkeypatch):
    # Run the background pipeline synchronously with fakes during tests.
    captured = {}

    def fake_run(meeting_id, store, transcriber, llm, llm_model, vad_trim, **kw):
        captured["ran"] = {"meeting_id": meeting_id, "vad_trim": vad_trim}

    monkeypatch.setattr("app.main.get_transcriber", lambda s: FakeTranscriber())
    monkeypatch.setattr("app.main.get_chat_model", lambda s: FakeLLM())
    monkeypatch.setattr("app.main.run_pipeline", fake_run)
    app = create_app(test_settings)
    return TestClient(app), captured


def test_upload_returns_meeting_id_and_schedules_pipeline(test_settings, monkeypatch):
    client, captured = _client(test_settings, monkeypatch)
    resp = client.post(
        "/meetings",
        files={"file": ("meeting.mp4", b"bytes", "video/mp4")},
        data={"vad_trim": "true"},
    )
    assert resp.status_code == 200
    mid = resp.json()["meeting_id"]
    assert mid
    assert captured["ran"]["meeting_id"] == mid
    assert captured["ran"]["vad_trim"] is True


def test_upload_rejects_unsupported_extension(test_settings, monkeypatch):
    client, _ = _client(test_settings, monkeypatch)
    resp = client.post(
        "/meetings",
        files={"file": ("notes.txt", b"bytes", "text/plain")},
        data={"vad_trim": "false"},
    )
    assert resp.status_code == 400
    assert "Unsupported" in resp.json()["detail"]
```

- [ ] **Step 3: Run it to verify it fails**

Run: `pytest tests/test_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.main'`.

- [ ] **Step 4: Write `backend/app/main.py`**

```python
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.llm.factory import get_chat_model
from app.pipeline import run_pipeline
from app.qa.answerer import answer_question
from app.storage import MeetingStorage
from app.transcription.factory import get_transcriber


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Meeting Capturer")
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    )

    store = MeetingStorage(settings.data_dir)
    # Validate provider config at startup (fail fast).
    transcriber = get_transcriber(settings)
    llm = get_chat_model(settings)

    app.state.settings = settings
    app.state.store = store
    app.state.transcriber = transcriber
    app.state.llm = llm

    @app.post("/meetings")
    async def create_meeting(
        background: BackgroundTasks,
        file: UploadFile = File(...),
        vad_trim: bool = Form(False),
    ):
        ext = Path(file.filename or "").suffix.lower()
        if ext not in settings.allowed_ext_set():
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
        data = await file.read()
        meeting_id = store.create_meeting(file.filename, data, vad_trim=vad_trim)
        background.add_task(
            run_pipeline, meeting_id, store, app.state.transcriber, app.state.llm,
            settings.llm_model, vad_trim, settings.vad_min_silence_sec,
        )
        return {"meeting_id": meeting_id}

    @app.get("/meetings/{meeting_id}/status")
    def get_status(meeting_id: str):
        if not store.exists(meeting_id):
            raise HTTPException(status_code=404, detail="Meeting not found")
        return store.load_job(meeting_id)

    @app.get("/meetings/{meeting_id}")
    def get_meeting(meeting_id: str):
        if not store.exists(meeting_id):
            raise HTTPException(status_code=404, detail="Meeting not found")
        job = store.load_job(meeting_id)
        if job.status.value != "done":
            raise HTTPException(status_code=409, detail=f"Meeting not ready: {job.status.value}")
        return {
            "transcript": store.load_transcript(meeting_id),
            "notes": store.load_notes(meeting_id),
        }

    @app.get("/meetings/{meeting_id}/notes.md")
    def get_notes_markdown(meeting_id: str):
        from fastapi.responses import PlainTextResponse
        if not store.exists(meeting_id):
            raise HTTPException(status_code=404, detail="Meeting not found")
        return PlainTextResponse(store.load_notes_markdown(meeting_id))

    @app.get("/meetings/{meeting_id}/qa")
    def get_qa(meeting_id: str):
        if not store.exists(meeting_id):
            raise HTTPException(status_code=404, detail="Meeting not found")
        return store.load_qa(meeting_id)

    @app.post("/meetings/{meeting_id}/ask")
    def ask(meeting_id: str, payload: dict):
        if not store.exists(meeting_id):
            raise HTTPException(status_code=404, detail="Meeting not found")
        question = (payload or {}).get("question", "").strip()
        if not question:
            raise HTTPException(status_code=400, detail="question is required")
        transcript = store.load_transcript(meeting_id)
        history = store.load_qa(meeting_id)
        entry = answer_question(transcript, question, history, app.state.llm)
        store.append_qa(meeting_id, entry)
        return entry

    return app


app = create_app() if __name__ != "__main__" else None
```

> Note: `app = create_app()` at import time requires valid provider config (real API keys in `.env`). In tests we call `create_app(test_settings)` directly and monkeypatch the factories, so the module-level instance is not used. For `uvicorn app.main:app` to work in dev, populate `.env` first.

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/test_api.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/tests/conftest.py backend/tests/test_api.py
git commit -m "feat: FastAPI app with upload and provider wiring"
```

---

## Task 15: API — status, results, and Q&A endpoints

**Files:**
- Modify: `backend/tests/test_api.py` (add lifecycle/Q&A cases)

The routes already exist from Task 14; this task locks their behavior with tests that seed storage directly.

- [ ] **Step 1: Add tests to `backend/tests/test_api.py`**

```python
from datetime import datetime

from app.models import Segment, StoredNotes, Transcript
from app.storage import MeetingStorage


def _seed_done_meeting(test_settings):
    store = MeetingStorage(test_settings.data_dir)
    mid = store.create_meeting("a.mp4", b"x", vad_trim=False)
    job = store.load_job(mid)
    job.status = job.status.__class__("done")
    job.percent = 100
    store.save_job(job)
    store.save_transcript(Transcript(
        meeting_id=mid, source_file="a.mp4", duration_sec=10, provider="fake",
        created_at=datetime(2026, 6, 15), speakers=["Speaker 1"],
        segments=[Segment(id=0, speaker="Speaker 1", start=0, end=4, text="Budget approved.")],
    ))
    store.save_notes(StoredNotes(
        summary="A summary.", meeting_id=mid, model="claude-test",
        generated_at=datetime(2026, 6, 15),
    ))
    store.save_notes_markdown(mid, "# a.mp4 — Notes\n")
    return store, mid


def test_status_404_for_unknown(test_settings, monkeypatch):
    client, _ = _client(test_settings, monkeypatch)
    assert client.get("/meetings/nope/status").status_code == 404


def test_get_meeting_returns_transcript_and_notes(test_settings, monkeypatch):
    client, _ = _client(test_settings, monkeypatch)
    _store, mid = _seed_done_meeting(test_settings)
    resp = client.get(f"/meetings/{mid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["notes"]["summary"] == "A summary."
    assert body["transcript"]["segments"][0]["text"] == "Budget approved."


def test_get_meeting_409_when_not_done(test_settings, monkeypatch):
    client, _ = _client(test_settings, monkeypatch)
    store = MeetingStorage(test_settings.data_dir)
    mid = store.create_meeting("a.mp4", b"x", vad_trim=False)  # still pending
    assert client.get(f"/meetings/{mid}").status_code == 409


def test_ask_appends_and_returns_answer(test_settings, monkeypatch):
    client, _ = _client(test_settings, monkeypatch)
    _store, mid = _seed_done_meeting(test_settings)
    resp = client.post(f"/meetings/{mid}/ask", json={"question": "Was budget approved?"})
    assert resp.status_code == 200
    assert resp.json()["answer"] == "A fake answer."
    qa = client.get(f"/meetings/{mid}/qa").json()
    assert len(qa) == 1 and qa[0]["question"] == "Was budget approved?"


def test_ask_requires_question(test_settings, monkeypatch):
    client, _ = _client(test_settings, monkeypatch)
    _store, mid = _seed_done_meeting(test_settings)
    assert client.post(f"/meetings/{mid}/ask", json={"question": "  "}).status_code == 400


def test_notes_markdown_endpoint(test_settings, monkeypatch):
    client, _ = _client(test_settings, monkeypatch)
    _store, mid = _seed_done_meeting(test_settings)
    resp = client.get(f"/meetings/{mid}/notes.md")
    assert resp.status_code == 200
    assert resp.text.startswith("# a.mp4 — Notes")
```

- [ ] **Step 2: Run the tests to verify they pass**

Run: `pytest tests/test_api.py -v`
Expected: all upload + lifecycle + Q&A tests pass (8 total).

- [ ] **Step 3: Run the full backend suite**

Run: `pytest -v`
Expected: all tests pass (ffmpeg test skipped only if ffmpeg is absent).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_api.py
git commit -m "test: API status, results, and Q&A endpoints"
```

---

## Task 16: Frontend scaffold, types, and API client

**Files:**
- Create: `frontend/` via Vite
- Create: `frontend/src/types.ts`
- Create: `frontend/src/api.ts`
- Create: `frontend/vite.config.ts` (add Vitest config)
- Test: `frontend/tests/api.test.ts`

- [ ] **Step 1: Scaffold the Vite React-TS app**

Run:
```bash
cd frontend  # if it does not exist, run from repo root: npm create vite@latest frontend -- --template react-ts
npm create vite@latest . -- --template react-ts
npm install
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
```

- [ ] **Step 2: Configure Vitest in `frontend/vite.config.ts`**

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/meetings": "http://localhost:8000" } },
  test: { environment: "jsdom", globals: true },
});
```

- [ ] **Step 3: Create `frontend/src/types.ts`**

```ts
export interface Segment { id: number; speaker: string; start: number; end: number; text: string; }
export interface Transcript {
  meeting_id: string; source_file: string; duration_sec: number;
  language: string | null; provider: string; created_at: string;
  speakers: string[]; segments: Segment[];
}
export interface ActionItem { task: string; owner: string | null; due: string | null; }
export interface TimelineEntry { start: number; topic: string; }
export interface Notes {
  meeting_id: string; model: string; generated_at: string; summary: string;
  action_items: ActionItem[]; decisions: string[];
  topic_timeline: TimelineEntry[]; open_questions: string[];
}
export type JobStatus =
  | "pending" | "extracting" | "transcribing" | "transcribed"
  | "generating_notes" | "done" | "failed";
export interface Job {
  meeting_id: string; source_file: string; vad_trim: boolean;
  status: JobStatus; stage: string; percent: number; error: string | null;
}
export interface QAEntry { question: string; answer: string; citations: string[]; }
export interface MeetingResult { transcript: Transcript; notes: Notes; }
```

- [ ] **Step 4: Create `frontend/src/api.ts`**

```ts
import type { Job, MeetingResult, QAEntry } from "./types";

export async function uploadMeeting(file: File, vadTrim: boolean): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  form.append("vad_trim", String(vadTrim));
  const res = await fetch("/meetings", { method: "POST", body: form });
  if (!res.ok) throw new Error((await res.json()).detail ?? "Upload failed");
  return (await res.json()).meeting_id;
}

export async function getStatus(meetingId: string): Promise<Job> {
  const res = await fetch(`/meetings/${meetingId}/status`);
  if (!res.ok) throw new Error("Failed to fetch status");
  return res.json();
}

export async function getMeeting(meetingId: string): Promise<MeetingResult> {
  const res = await fetch(`/meetings/${meetingId}`);
  if (!res.ok) throw new Error("Failed to fetch meeting");
  return res.json();
}

export async function askQuestion(meetingId: string, question: string): Promise<QAEntry> {
  const res = await fetch(`/meetings/${meetingId}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? "Question failed");
  return res.json();
}
```

- [ ] **Step 5: Write `frontend/tests/api.test.ts`**

```ts
import { describe, expect, it, vi, beforeEach } from "vitest";
import { uploadMeeting } from "../src/api";

describe("uploadMeeting", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("posts the file and returns the meeting id", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ meeting_id: "abc123" }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const file = new File([new Uint8Array([1, 2])], "a.mp4", { type: "video/mp4" });
    const id = await uploadMeeting(file, true);
    expect(id).toBe("abc123");
    expect(fetchMock).toHaveBeenCalledWith("/meetings", expect.objectContaining({ method: "POST" }));
  });

  it("throws with backend detail on failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false, json: async () => ({ detail: "Unsupported file type: .txt" }),
    }));
    const file = new File([new Uint8Array([1])], "a.txt", { type: "text/plain" });
    await expect(uploadMeeting(file, false)).rejects.toThrow("Unsupported file type");
  });
});
```

- [ ] **Step 6: Add a test script to `frontend/package.json`**

In the `"scripts"` block add: `"test": "vitest run"`.

- [ ] **Step 7: Run the test**

Run: `cd frontend && npm test`
Expected: 2 passed.

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "feat: frontend scaffold, types, and API client"
```

---

## Task 17: Upload and Progress views

**Files:**
- Create: `frontend/src/components/UploadView.tsx`
- Create: `frontend/src/components/ProgressView.tsx`
- Test: `frontend/tests/UploadView.test.tsx`

- [ ] **Step 1: Create `frontend/src/components/UploadView.tsx`**

```tsx
import { useState } from "react";

interface Props {
  onUpload: (file: File, vadTrim: boolean) => void;
  disabled?: boolean;
  error?: string | null;
}

export function UploadView({ onUpload, disabled, error }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [vadTrim, setVadTrim] = useState(false);

  return (
    <div className="upload-view">
      <h2>Upload a meeting recording</h2>
      <input
        type="file"
        accept=".mp4,.mkv,.mov,.webm,.mp3,.m4a,.wav"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
      />
      <label>
        <input
          type="checkbox"
          checked={vadTrim}
          onChange={(e) => setVadTrim(e.target.checked)}
        />
        Trim silence (cheaper transcription)
      </label>
      <button
        disabled={!file || disabled}
        onClick={() => file && onUpload(file, vadTrim)}
      >
        Process meeting
      </button>
      {error && <p className="error" role="alert">{error}</p>}
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/components/ProgressView.tsx`**

```tsx
import type { Job } from "../types";

const STAGE_LABELS: Record<string, string> = {
  pending: "Queued",
  extracting: "Extracting audio",
  transcribing: "Transcribing & diarizing",
  transcribed: "Transcription complete",
  generating_notes: "Generating notes",
  done: "Done",
  failed: "Failed",
};

export function ProgressView({ job }: { job: Job }) {
  return (
    <div className="progress-view">
      <h2>Processing {job.source_file}</h2>
      <progress max={100} value={job.percent} />
      <p>{STAGE_LABELS[job.status] ?? job.stage} ({job.percent}%)</p>
      {job.status === "failed" && (
        <p className="error" role="alert">Error: {job.error}</p>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Write `frontend/tests/UploadView.test.tsx`**

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { UploadView } from "../src/components/UploadView";

describe("UploadView", () => {
  it("calls onUpload with the file and vadTrim flag", () => {
    const onUpload = vi.fn();
    render(<UploadView onUpload={onUpload} />);

    const file = new File([new Uint8Array([1])], "a.mp4", { type: "video/mp4" });
    const input = screen.getByDisplayValue("") as HTMLInputElement;
    fireEvent.change(screen.getByRole("checkbox"));
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /process meeting/i }));

    expect(onUpload).toHaveBeenCalledWith(file, true);
  });

  it("shows an error message when provided", () => {
    render(<UploadView onUpload={vi.fn()} error="Unsupported file type" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Unsupported file type");
  });
});
```

- [ ] **Step 4: Run the test**

Run: `cd frontend && npm test`
Expected: all passing (api + UploadView).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/UploadView.tsx frontend/src/components/ProgressView.tsx frontend/tests/UploadView.test.tsx
git commit -m "feat: upload and progress views"
```

---

## Task 18: Results views and Q&A chat

**Files:**
- Create: `frontend/src/components/NotesTab.tsx`
- Create: `frontend/src/components/TranscriptTab.tsx`
- Create: `frontend/src/components/QAChat.tsx`
- Create: `frontend/src/components/ResultsView.tsx`

- [ ] **Step 1: Create `frontend/src/components/NotesTab.tsx`**

```tsx
import type { Notes } from "../types";

function mmss(seconds: number): string {
  const t = Math.floor(seconds);
  return `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`;
}

interface Props { notes: Notes; onJumpToTime: (start: number) => void; }

export function NotesTab({ notes, onJumpToTime }: Props) {
  return (
    <div className="notes-tab">
      <section>
        <h3>Summary</h3>
        <p>{notes.summary}</p>
      </section>

      {notes.action_items.length > 0 && (
        <section>
          <h3>Action Items</h3>
          <ul>
            {notes.action_items.map((a, i) => (
              <li key={i}>
                <input type="checkbox" readOnly />
                {a.owner ? <strong>{a.owner} — </strong> : null}
                {a.task}
                {a.due ? ` (due ${a.due})` : ""}
              </li>
            ))}
          </ul>
        </section>
      )}

      {notes.decisions.length > 0 && (
        <section>
          <h3>Decisions</h3>
          <ul>{notes.decisions.map((d, i) => <li key={i}>{d}</li>)}</ul>
        </section>
      )}

      {notes.topic_timeline.length > 0 && (
        <section>
          <h3>Topic Timeline</h3>
          <ul>
            {notes.topic_timeline.map((t, i) => (
              <li key={i}>
                <button className="ts-link" onClick={() => onJumpToTime(t.start)}>
                  [{mmss(t.start)}]
                </button>{" "}
                {t.topic}
              </li>
            ))}
          </ul>
        </section>
      )}

      {notes.open_questions.length > 0 && (
        <section>
          <h3>Open Questions</h3>
          <ul>{notes.open_questions.map((q, i) => <li key={i}>{q}</li>)}</ul>
        </section>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/components/TranscriptTab.tsx`**

The timeline "jump" resolves to the segment whose `start` is the closest at or before the target time (anchored by segment, per spec §4).

```tsx
import { useEffect, useRef } from "react";
import type { Transcript } from "../types";

function mmss(seconds: number): string {
  const t = Math.floor(seconds);
  return `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`;
}

interface Props { transcript: Transcript; jumpToTime: number | null; }

export function TranscriptTab({ transcript, jumpToTime }: Props) {
  const refs = useRef<Record<number, HTMLDivElement | null>>({});

  useEffect(() => {
    if (jumpToTime == null) return;
    // nearest segment at or before the target time
    let target = transcript.segments[0];
    for (const seg of transcript.segments) {
      if (seg.start <= jumpToTime) target = seg;
      else break;
    }
    refs.current[target?.id]?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [jumpToTime, transcript]);

  return (
    <div className="transcript-tab">
      {transcript.segments.map((seg) => (
        <div key={seg.id} ref={(el) => { refs.current[seg.id] = el; }} className="segment">
          <span className="ts">[{mmss(seg.start)}]</span>{" "}
          <strong>{seg.speaker}:</strong> {seg.text}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Create `frontend/src/components/QAChat.tsx`**

```tsx
import { useState } from "react";
import type { QAEntry } from "../types";
import { askQuestion } from "../api";

export function QAChat({ meetingId }: { meetingId: string }) {
  const [history, setHistory] = useState<QAEntry[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!question.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const entry = await askQuestion(meetingId, question);
      setHistory((h) => [...h, entry]);
      setQuestion("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="qa-chat">
      <h3>Ask about this meeting</h3>
      <div className="qa-history">
        {history.map((e, i) => (
          <div key={i} className="qa-entry">
            <p className="qa-q"><strong>Q:</strong> {e.question}</p>
            <p className="qa-a"><strong>A:</strong> {e.answer}</p>
          </div>
        ))}
      </div>
      <div className="qa-input">
        <input
          value={question}
          placeholder="e.g. What were the action items?"
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
        <button disabled={busy} onClick={submit}>Ask</button>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
    </div>
  );
}
```

- [ ] **Step 4: Create `frontend/src/components/ResultsView.tsx`**

```tsx
import { useState } from "react";
import type { MeetingResult } from "../types";
import { NotesTab } from "./NotesTab";
import { TranscriptTab } from "./TranscriptTab";
import { QAChat } from "./QAChat";

export function ResultsView({ result }: { result: MeetingResult }) {
  const [tab, setTab] = useState<"notes" | "transcript">("notes");
  const [jumpToTime, setJumpToTime] = useState<number | null>(null);

  function jump(start: number) {
    setTab("transcript");
    setJumpToTime(start);
  }

  return (
    <div className="results-view">
      <div className="tabs">
        <button onClick={() => setTab("notes")} aria-pressed={tab === "notes"}>Notes</button>
        <button onClick={() => setTab("transcript")} aria-pressed={tab === "transcript"}>Transcript</button>
        <a href={`/meetings/${result.notes.meeting_id}/notes.md`} download>Export Markdown</a>
      </div>

      {tab === "notes"
        ? <NotesTab notes={result.notes} onJumpToTime={jump} />
        : <TranscriptTab transcript={result.transcript} jumpToTime={jumpToTime} />}

      <QAChat meetingId={result.notes.meeting_id} />
    </div>
  );
}
```

- [ ] **Step 5: Run the existing tests (no regressions)**

Run: `cd frontend && npm test`
Expected: still passing.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/
git commit -m "feat: results views and Q&A chat"
```

---

## Task 19: App wiring with status polling

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/main.tsx` (ensure it renders `<App />` — default from scaffold)

`App` owns the flow: `upload → polling → results`, polling status every 2s until `done`/`failed`.

- [ ] **Step 1: Replace `frontend/src/App.tsx`**

```tsx
import { useEffect, useRef, useState } from "react";
import { UploadView } from "./components/UploadView";
import { ProgressView } from "./components/ProgressView";
import { ResultsView } from "./components/ResultsView";
import { getMeeting, getStatus, uploadMeeting } from "./api";
import type { Job, MeetingResult } from "./types";

type Phase = "upload" | "processing" | "done";

export default function App() {
  const [phase, setPhase] = useState<Phase>("upload");
  const [job, setJob] = useState<Job | null>(null);
  const [result, setResult] = useState<MeetingResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const meetingId = useRef<string | null>(null);

  async function handleUpload(file: File, vadTrim: boolean) {
    setError(null);
    try {
      const id = await uploadMeeting(file, vadTrim);
      meetingId.current = id;
      setPhase("processing");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    if (phase !== "processing" || !meetingId.current) return;
    const id = meetingId.current;
    const timer = setInterval(async () => {
      try {
        const status = await getStatus(id);
        setJob(status);
        if (status.status === "done") {
          clearInterval(timer);
          setResult(await getMeeting(id));
          setPhase("done");
        } else if (status.status === "failed") {
          clearInterval(timer);
        }
      } catch (e) {
        setError((e as Error).message);
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [phase]);

  return (
    <main className="app">
      <h1>Meeting Capturer</h1>
      {phase === "upload" && <UploadView onUpload={handleUpload} error={error} />}
      {phase === "processing" && job && <ProgressView job={job} />}
      {phase === "done" && result && <ResultsView result={result} />}
    </main>
  );
}
```

- [ ] **Step 2: Run tests and type-check**

Run: `cd frontend && npm test && npx tsc --noEmit`
Expected: tests pass; no type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx frontend/src/main.tsx
git commit -m "feat: app flow with status polling"
```

---

## Task 20: End-to-end smoke test and run docs

**Files:**
- Create: `backend/tests/test_smoke.py`
- Create: `README.md` run section (modify existing root `README.md`)

The smoke test exercises the real pipeline wiring with fakes for the network-bound providers, but real ffmpeg + storage, proving the stages connect end-to-end.

- [ ] **Step 1: Write `backend/tests/test_smoke.py`**

```python
import shutil
import subprocess

import pytest

import app.pipeline as pipeline_mod
from app.models import JobStatus, Notes, Segment, TranscriptionResult
from app.pipeline import run_pipeline
from app.storage import MeetingStorage

ffmpeg_available = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


class FakeTranscriber:
    name = "fake"

    def transcribe(self, audio_path, language=None):
        return TranscriptionResult(
            provider="fake", language="en",
            segments=[Segment(id=0, speaker="Speaker 1", start=0, end=2, text="Smoke test.")],
        )


class _Structured:
    def invoke(self, messages):
        return Notes(summary="Smoke summary.")


class FakeLLM:
    def with_structured_output(self, schema):
        return _Structured()


@pytest.mark.skipif(not ffmpeg_available, reason="ffmpeg/ffprobe not installed")
def test_end_to_end_with_real_ffmpeg(tmp_path):
    # Make a 2s tone "recording" and run the full pipeline (real extract, fake providers).
    src = tmp_path / "rec.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-ar", "44100", str(src)],
        check=True, capture_output=True,
    )
    store = MeetingStorage(tmp_path / "data")
    mid = store.create_meeting("rec.wav", src.read_bytes(), vad_trim=False)

    run_pipeline(mid, store, FakeTranscriber(), FakeLLM(), "claude-test", vad_trim=False)

    job = store.load_job(mid)
    assert job.status == JobStatus.done
    assert store.load_transcript(mid).segments[0].text == "Smoke test."
    assert store.load_notes(mid).summary == "Smoke summary."
    assert "# rec.wav — Notes" in store.load_notes_markdown(mid)
```

- [ ] **Step 2: Run the smoke test**

Run: `cd backend && pytest tests/test_smoke.py -v`
Expected: 1 passed (skipped if ffmpeg absent — install ffmpeg to run it).

- [ ] **Step 3: Update root `README.md` with run instructions**

Append this section to `README.md`:

```markdown
## Running locally (v1)

Prerequisites: Python 3.11+, Node 18+, and **ffmpeg** on PATH.

### Backend
```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
cp .env.example .env   # then fill in OPENAI_API_KEY and ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev   # opens Vite dev server, proxies /meetings to localhost:8000
```

Open the Vite URL, upload a recording, watch progress, then read notes and ask questions.

### Tests
- Backend: `cd backend && pytest`
- Frontend: `cd frontend && npm test`
```

- [ ] **Step 4: Run both full test suites**

Run: `cd backend && pytest` then `cd ../frontend && npm test`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_smoke.py README.md
git commit -m "test: end-to-end smoke test and run docs"
```

---

## Self-Review

**Spec coverage check** (against `2026-06-15-meeting-capturer-v1-design.md`):

- §2.1 Frontend (upload + toggle, progress, notes/transcript tabs, Q&A, export) → Tasks 16–19. ✓
- §2.1 Backend endpoints (`POST /meetings`, `GET status`, `GET meeting`, `POST ask`, `GET qa`, `notes.md`) → Tasks 14–15. ✓
- §2.1 Background task + status writes → Task 13. ✓
- §3 Storage layout (source, audio.wav, job.json, transcript.json, notes.json, notes.md, qa.json) → Task 4; write-ordering (transcript before notes) → Task 13. ✓
- §4 Canonical transcript format + segment-id navigation + best-effort timestamps → Tasks 2, 18 (TranscriptTab nearest-segment jump). ✓
- §5.1–5.2 Transcriber interface + OpenAI diarized adapter (`diarized_json`, `chunking_strategy="auto"`) → Tasks 7–8. ✓
- §5.4 Optional Silero VAD trim (default OFF, toggle, no remapping) → Tasks 5–6 (trim), 13 (conditional invoke), 16–17 (toggle). ✓
- §6 Structured notes (5 sections) + markdown render → Tasks 10–11. ✓
- §7 Full-transcript Q&A + history → Task 12. ✓
- §8 Config (env, provider selection, fail-fast) → Tasks 1, 8, 9, 14. ✓
- §9 Error handling (validation, never-stuck job, Q&A errors) → Tasks 13 (failed status), 14 (extension validation), 18 (Q&A error display). ✓
- §10 Testing (fakes, adapter contract, API, frontend, smoke) → Tasks throughout + 20. ✓
- §11 Module boundaries → matches File Structure. ✓

**Deferred (correctly not in plan):** prompt caching is noted in §7 as a cost optimization; the Q&A path (Task 12) passes the full transcript and is structured so a provider-specific `cache_control` block can be added later without interface changes. Named-speaker reference clips, Deepgram/AssemblyAI adapters, local Whisper, and timestamp remapping are all explicitly out of scope.

**Placeholder scan:** No TBD/TODO; every code step contains complete, runnable code and exact commands. ✓

**Type consistency:** `run_pipeline(meeting_id, store, transcriber, llm, llm_model, vad_trim, vad_min_silence_sec=...)` signature is identical in Task 13 (definition), Task 14 (`background.add_task`), and Task 13/20 tests. `MeetingStorage` method names (`create_meeting`, `load_job`/`save_job`, `save_transcript`/`load_transcript`, `save_notes`/`load_notes`, `save_notes_markdown`/`load_notes_markdown`, `append_qa`/`load_qa`, `exists`, `source_path`, `audio_path`) are used consistently across Tasks 4, 13, 14, 15, 20. `Notes`/`StoredNotes`/`TranscriptionResult` field names match between models (Task 2) and all consumers. Frontend `types.ts` mirrors backend JSON field names. ✓
