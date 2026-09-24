# Repo Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn two working-but-unpackaged Agent Skills into an installable, tested, documented repository that someone else can set up from a single command.

**Architecture:** The five existing scripts become an importable package under `src/meeting_digest/`, fronted by a single `meeting-digest` console command. Logic currently trapped inside `main()` moves into modules that take plain values, so it can be unit-tested; argparse consolidates in `cli.py`. The two skills move under `skills/` and document the CLI instead of script paths. The artifact formats both skills depend on become a written contract with runtime validation.

**Tech Stack:** Python 3.10+, argparse, numpy, opencv-python-headless, faster-whisper, pyannote.audio, FFmpeg/ffprobe, pytest, ruff, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-24-repo-foundation-design.md`

## Global Constraints

- Package name `meeting-digest`; import name `meeting_digest`; repo name `meeting-digest`.
- Python `>=3.10`. All dependencies are required — no optional extras.
- Dependency floors: `numpy>=2,<3`, `opencv-python-headless>=4.10`, `faster-whisper>=1.1`, `pyannote.audio>=3.3`. Lower bounds only, never exact pins (the current `requirements.txt` exact pins are replaced).
- Existing behavior is preserved. Flags, defaults, output filenames, JSON keys, and the refuse-to-overwrite rule stay exactly as they are today. The one intentional change is the `probe()` duration fallback in Task 5.
- All JSON and Markdown output is written UTF-8. Transcript JSON uses `ensure_ascii=False`.
- Errors the user should see are raised as `DigestError` and printed as `error: <message>` with exit code 2. Never let a traceback reach the user for an expected failure.
- Speaker labels are `Speaker N`, assigned by first occurrence. Never infer real names.
- `ruff` is the only linter/formatter. Line length 100.
- Every commit message uses a Conventional Commits prefix (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`, `build:`, `ci:`).

## Execution Batches

Checkpoints are batched, not per-task. Stop for review at the end of each batch only.

| Batch | Tasks | Review gate |
|---|---|---|
| A | 1–2 | Repo is pivoted and `pip install -e .` works |
| B | 3–5 | Foundation modules green |
| C | 6–10 | All pipeline modules ported, unit tests green |
| D | 11–12 | CLI complete, every command runs |
| E | 13 | E2E test passes against generated media |
| F | 14–15 | CI green, skills updated |
| G | 16 | Docs complete |

---

# Batch A — Repo pivot and packaging

### Task 1: Pivot the repository

**Files:**
- Delete: `old/` (entire directory), `backend/` (all tracked paths), `docs/superpowers/plans/2026-06-15-meeting-capturer-v1.md`, `docs/superpowers/specs/2026-06-15-meeting-capturer-v1-design.md`
- Move: `meeting-digest/` → `skills/meeting-digest/`, `meeting-assistant/` → `skills/meeting-assistant/`
- Delete: `skills/meeting-digest/requirements.txt` (superseded by `pyproject.toml` in Task 2)
- Create: `.gitignore`, `LICENSE`
- Modify: `README.md` (replace the backend's entirely — a stub here, filled in Task 16)

**Interfaces:**
- Consumes: nothing.
- Produces: the directory layout every later task writes into — `skills/meeting-digest/`, `skills/meeting-assistant/`, and a clean tracked tree containing no `backend/`.

- [ ] **Step 1: Confirm `old/` is redundant before deleting it**

`old/` is an untracked copy of content already in git history. Verify that before removing it:

```bash
git log --oneline -- backend/ | head
ls old/
```

Expected: history shows the backend commits, and `old/` contains `LICENSE README.md backend/ docs/`. If `old/` contains anything *not* in history, stop and report it rather than deleting.

- [ ] **Step 2: Remove the abandoned backend from tracking**

```bash
git rm -r --cached backend/ -q
git rm --cached docs/superpowers/plans/2026-06-15-meeting-capturer-v1.md -q
git rm --cached docs/superpowers/specs/2026-06-15-meeting-capturer-v1-design.md -q
rm -rf old/
```

The working tree already shows these as deleted; this stages the deletion.

- [ ] **Step 3: Move both skills under `skills/`**

```bash
mkdir -p skills
git mv meeting-digest skills/meeting-digest 2>/dev/null || mv meeting-digest skills/meeting-digest
git mv meeting-assistant skills/meeting-assistant 2>/dev/null || mv meeting-assistant skills/meeting-assistant
rm -f skills/meeting-digest/requirements.txt
```

Both directories are currently untracked, so `git mv` will fail and the `mv` fallback runs. That is expected.

- [ ] **Step 4: Write `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
build/
dist/
.venv/
venv/

# Tooling
.pytest_cache/
.ruff_cache/
.coverage
htmlcov/

# Editors / OS
.vscode/
.idea/
.DS_Store
Thumbs.db

# Meeting artifacts — recordings and derived output never belong in git
meetings/
*.mp4
*.mkv
*.mov
*.wav
```

- [ ] **Step 5: Write `LICENSE`**

MIT, copyright `2026 Davin Dewanto`. Use the standard MIT text verbatim.

- [ ] **Step 6: Write a stub `README.md`**

```markdown
# meeting-digest

Turn recorded meetings into speaker-labeled transcripts, presentation
screenshots, and evidence-linked notes — then ask questions about them.

Two Claude Agent Skills plus the local command-line tooling they drive.

Full documentation is being written; see `docs/` for the design.
```

- [ ] **Step 7: Verify the tree**

```bash
git add -A
git status --short
```

Expected: `backend/*` and the two v1 doc files staged as deleted; `skills/meeting-digest/*`, `skills/meeting-assistant/*`, `.gitignore`, `LICENSE`, `README.md` staged as added. No `old/` and no top-level `meeting-digest/` or `meeting-assistant/`.

- [ ] **Step 8: Commit**

```bash
git commit -m "chore: pivot repo to the meeting-digest and meeting-assistant skills

Removes the abandoned FastAPI backend and its v1 design docs, moves both
skills under skills/, and adds a root .gitignore and MIT license."
```

- [ ] **Step 9: Rename the repository**

This step needs the user. Report to them:

> Rename the GitHub repo `meeting_capturer` → `meeting-digest` in Settings → General, then tell me when it's done.

After they confirm:

```bash
git remote set-url origin https://github.com/davin-advasol/meeting-digest.git
git remote -v
```

Expected: both fetch and push show the new URL. The local directory rename is also the user's to do — it cannot be renamed from inside itself.

---

### Task 2: Package skeleton

**Files:**
- Create: `pyproject.toml`, `src/meeting_digest/__init__.py`, `src/meeting_digest/cli.py`
- Create: `tests/__init__.py`, `tests/test_cli_smoke.py`

**Interfaces:**
- Consumes: Task 1's layout.
- Produces: `meeting_digest.__version__` (str); `meeting_digest.cli.main() -> int`; an installed `meeting-digest` console command. Every later task adds subparsers to `cli.build_parser()`.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "meeting-digest"
version = "0.1.0"
description = "Turn recorded meetings into speaker-labeled transcripts, screenshots, and evidence-linked notes"
readme = "README.md"
requires-python = ">=3.10"
license = { file = "LICENSE" }
authors = [{ name = "Davin Dewanto" }]
keywords = ["meetings", "transcription", "diarization", "claude", "agent-skill"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Multimedia :: Sound/Audio :: Speech",
]
dependencies = [
    "numpy>=2,<3",
    "opencv-python-headless>=4.10",
    "faster-whisper>=1.1",
    "pyannote.audio>=3.3",
]

[project.optional-dependencies]
dev = ["pytest>=8", "ruff>=0.6"]

[project.urls]
Homepage = "https://github.com/davin-advasol/meeting-digest"
Issues = "https://github.com/davin-advasol/meeting-digest/issues"

[project.scripts]
meeting-digest = "meeting_digest.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/meeting_digest"]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["slow: needs ffmpeg and real media generation"]
```

`dev` is a tooling extra, not a runtime one — it does not contradict the "all dependencies required" decision, which is about the pipeline's own dependencies.

- [ ] **Step 2: Write `src/meeting_digest/__init__.py`**

```python
"""Local meeting ingestion: audio, screenshots, transcripts, speaker labels."""

__version__ = "0.1.0"

__all__ = ["__version__"]
```

- [ ] **Step 3: Write the minimal `src/meeting_digest/cli.py`**

Subcommands arrive in Tasks 11–12. This establishes the entry point and the error contract.

```python
"""Command-line front door. Parses arguments and dispatches to the modules."""
from __future__ import annotations

import argparse
import sys

from meeting_digest import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meeting-digest",
        description="Turn recorded meetings into transcripts, screenshots, and notes.",
    )
    parser.add_argument("--version", action="version", version=f"meeting-digest {__version__}")
    parser.add_subparsers(dest="command", metavar="COMMAND")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Write the smoke test**

`tests/__init__.py` is empty. `tests/test_cli_smoke.py`:

```python
import subprocess
import sys

import pytest

from meeting_digest import __version__
from meeting_digest.cli import build_parser, main


def test_version_is_a_string():
    assert isinstance(__version__, str)
    assert __version__.count(".") == 2


def test_parser_builds():
    assert build_parser().prog == "meeting-digest"


def test_no_command_prints_help_and_returns_1(capsys):
    assert main([]) == 1
    assert "usage: meeting-digest" in capsys.readouterr().out


def test_version_flag_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_installed_console_script_runs():
    result = subprocess.run(
        [sys.executable, "-m", "meeting_digest.cli", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert __version__ in result.stdout
```

- [ ] **Step 5: Install and run**

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/test_cli_smoke.py -v
```

Expected: 5 passed. The install pulls Torch on a cold machine — this is the slow step, once.

- [ ] **Step 6: Verify the console script exists**

```bash
meeting-digest --version
```

Expected: `meeting-digest 0.1.0`. If `command not found`, the install did not create the script — re-run step 5 and read its output rather than working around it.

- [ ] **Step 7: Lint**

```bash
ruff check . && ruff format --check .
```

Expected: no errors. If `ruff format --check` reports files, run `ruff format .` and re-check.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml src/ tests/
git commit -m "build: add installable package skeleton and meeting-digest console script"
```

**BATCH A CHECKPOINT — stop for review.**

---

# Batch B — Foundation modules

### Task 3: `errors.py`

**Files:**
- Create: `src/meeting_digest/errors.py`
- Test: `tests/test_errors.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `class DigestError(Exception)`. Every module raises it for user-facing failures; `cli.main()` catches it in Task 11.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from meeting_digest.errors import DigestError


def test_digest_error_is_an_exception():
    assert issubclass(DigestError, Exception)


def test_digest_error_carries_its_message():
    with pytest.raises(DigestError) as exc:
        raise DigestError("recording has no audio stream")
    assert str(exc.value) == "recording has no audio stream"
```

- [ ] **Step 2: Run it and watch it fail**

Run: `python -m pytest tests/test_errors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'meeting_digest.errors'`

- [ ] **Step 3: Implement**

```python
"""The one exception type the CLI turns into a clean message."""
from __future__ import annotations


class DigestError(Exception):
    """A failure the user can act on.

    Raised for bad input, missing dependencies, and unusable media. The CLI
    prints these as `error: <message>` and exits 2, never as a traceback.
    """
```

- [ ] **Step 4: Run it and watch it pass**

Run: `python -m pytest tests/test_errors.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/meeting_digest/errors.py tests/test_errors.py
git commit -m "feat: add DigestError for user-facing failures"
```

---

### Task 4: `timeline.py`

This kills both duplications: `stamp()` exists identically in `scripts/transcribe_local.py:8` and `scripts/label_speakers.py:8`, and the ffprobe offset calculation exists in `scripts/extract_audio.py:20-21` and `scripts/select_frames.py:69-70` with **divergent** behavior — `select_frames` clamps negatives to zero, `extract_audio` does not.

**Files:**
- Create: `src/meeting_digest/timeline.py`
- Test: `tests/test_timeline.py`

**Interfaces:**
- Consumes: `DigestError` from Task 3.
- Produces:
  - `stamp(seconds: float) -> str` — `HH:MM:SS.mmm`
  - `stream_offset(probe_data: dict, stream: dict, *, clamp: bool) -> float`
  - `container_duration(probe_data: dict, stream: dict) -> float`

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from meeting_digest.errors import DigestError
from meeting_digest.timeline import container_duration, stamp, stream_offset


def test_stamp_formats_hours_minutes_seconds_milliseconds():
    assert stamp(0) == "00:00:00.000"
    assert stamp(1.5) == "00:00:01.500"
    assert stamp(61.25) == "00:01:01.250"
    assert stamp(3723.004) == "01:02:03.004"


def test_stamp_rounds_to_the_nearest_millisecond():
    assert stamp(1.23456) == "00:00:01.235"


def _probe(format_start, stream_start):
    data = {"format": {"start_time": format_start, "duration": "10.0"}, "streams": []}
    stream = {} if stream_start is None else {"start_time": stream_start}
    return data, stream


def test_stream_offset_is_zero_when_streams_are_aligned():
    data, stream = _probe("0.0", "0.0")
    assert stream_offset(data, stream, clamp=False) == 0.0


def test_stream_offset_is_positive_when_the_stream_starts_late():
    data, stream = _probe("0.0", "0.5")
    assert stream_offset(data, stream, clamp=False) == pytest.approx(0.5)


def test_stream_offset_is_negative_when_the_stream_starts_early():
    data, stream = _probe("0.5", "0.0")
    assert stream_offset(data, stream, clamp=False) == pytest.approx(-0.5)


def test_stream_offset_clamps_negatives_when_asked():
    data, stream = _probe("0.5", "0.0")
    assert stream_offset(data, stream, clamp=True) == 0.0


def test_stream_offset_falls_back_to_the_container_origin():
    data, stream = _probe("0.25", None)
    assert stream_offset(data, stream, clamp=False) == 0.0


def test_container_duration_prefers_the_format_value():
    data = {"format": {"duration": "12.5"}}
    assert container_duration(data, {"duration": "99"}) == pytest.approx(12.5)


def test_container_duration_falls_back_to_the_stream():
    data = {"format": {}}
    assert container_duration(data, {"duration": "12.5"}) == pytest.approx(12.5)


def test_container_duration_raises_when_neither_is_present():
    with pytest.raises(DigestError, match="duration"):
        container_duration({"format": {}}, {})
```

- [ ] **Step 2: Run them and watch them fail**

Run: `python -m pytest tests/test_timeline.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'meeting_digest.timeline'`

- [ ] **Step 3: Implement**

```python
"""Timestamp formatting and audio/video stream offset arithmetic.

Both concerns used to be duplicated across the scripts, and the two copies of
the offset calculation disagreed about negative offsets. `clamp` makes that
difference explicit instead of accidental.
"""
from __future__ import annotations

from meeting_digest.errors import DigestError


def stamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS.mmm."""
    ms = round(seconds * 1000)
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02}.{ms % 1000:03}"


def stream_offset(probe_data: dict, stream: dict, *, clamp: bool) -> float:
    """Return a stream's start time relative to the container origin.

    A positive result means the stream starts after the container. Audio
    extraction needs the signed value so it can pad or trim; frame scanning
    uses it as a timeline base, where a negative value is meaningless, so it
    passes `clamp=True`.
    """
    origin = float(probe_data.get("format", {}).get("start_time", 0))
    offset = float(stream.get("start_time", origin)) - origin
    return max(0.0, offset) if clamp else offset


def container_duration(probe_data: dict, stream: dict) -> float:
    """Return the media duration in seconds.

    Some containers — fragmented MP4, certain MKV files — omit
    `format.duration`. Fall back to the stream's own duration before failing.
    """
    for source in (probe_data.get("format", {}), stream):
        value = source.get("duration")
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    raise DigestError(
        "Could not determine the recording duration: neither the container nor the "
        "stream reports one. Try remuxing with `ffmpeg -i <input> -c copy <output>.mp4`."
    )
```

- [ ] **Step 4: Run them and watch them pass**

Run: `python -m pytest tests/test_timeline.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add src/meeting_digest/timeline.py tests/test_timeline.py
git commit -m "feat: add timeline module for stamps and stream offsets

Deduplicates stamp() and the ffprobe offset block, and makes the negative-offset
clamping difference between audio and video explicit. Adds a duration fallback
for containers that omit format.duration."
```

---

### Task 5: `ffmpeg.py`

**Files:**
- Create: `src/meeting_digest/ffmpeg.py`
- Test: `tests/test_ffmpeg.py`

**Interfaces:**
- Consumes: `DigestError` (Task 3).
- Produces:
  - `dependencies() -> dict[str, bool]`
  - `probe(path: Path) -> dict`
  - `select_stream(probe_data: dict, codec_type: str) -> dict`
  - `run(args: list[str]) -> None`
  - `stream_gray_frames(video, stream_index, filters, width, height) -> Iterator[np.ndarray]`

- [ ] **Step 1: Write the failing tests**

Only the pure parts are unit-tested; `probe` and `stream_gray_frames` are covered by the E2E test in Task 13.

```python
from pathlib import Path

import pytest

from meeting_digest.errors import DigestError
from meeting_digest.ffmpeg import dependencies, run, select_stream


def test_dependencies_reports_the_four_requirements():
    assert set(dependencies()) == {"ffmpeg", "ffprobe", "numpy", "cv2"}


def test_dependencies_values_are_booleans():
    assert all(isinstance(v, bool) for v in dependencies().values())


def test_select_stream_returns_the_first_matching_stream():
    data = {
        "streams": [
            {"codec_type": "audio", "index": 0},
            {"codec_type": "video", "index": 1},
        ]
    }
    assert select_stream(data, "video")["index"] == 1


def test_select_stream_skips_attached_cover_art():
    data = {
        "streams": [
            {"codec_type": "video", "index": 0, "disposition": {"attached_pic": 1}},
            {"codec_type": "video", "index": 1},
        ]
    }
    assert select_stream(data, "video")["index"] == 1


def test_select_stream_raises_when_nothing_matches():
    with pytest.raises(DigestError, match="no audio stream"):
        select_stream({"streams": [{"codec_type": "video", "index": 0}]}, "audio")


def test_run_raises_digest_error_with_the_stderr_text():
    with pytest.raises(DigestError) as exc:
        run(["ffmpeg", "-v", "error", "-i", str(Path("does-not-exist.mp4")), "-f", "null", "-"])
    assert "does-not-exist.mp4" in str(exc.value)
```

- [ ] **Step 2: Run them and watch them fail**

Run: `python -m pytest tests/test_ffmpeg.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'meeting_digest.ffmpeg'`

- [ ] **Step 3: Implement**

The `stream_gray_frames` body is the decode loop lifted from `scripts/select_frames.py:87-119`, unchanged apart from yielding frames instead of calling a selector.

```python
"""Every subprocess call to ffmpeg and ffprobe lives here.

Isolating them means the rest of the package is pure enough to unit-test.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

from meeting_digest.errors import DigestError

_REQUIRED_BINARIES = ("ffmpeg", "ffprobe")
_REQUIRED_MODULES = ("numpy", "cv2")


def dependencies() -> dict[str, bool]:
    """Report which external requirements are present."""
    found = {name: bool(shutil.which(name)) for name in _REQUIRED_BINARIES}
    found.update({name: importlib.util.find_spec(name) is not None for name in _REQUIRED_MODULES})
    return found


def require_dependencies() -> None:
    missing = [name for name, present in dependencies().items() if not present]
    if missing:
        raise DigestError(
            "Missing dependencies: "
            + ", ".join(missing)
            + ". FFmpeg and ffprobe are separate executables that must be on PATH; "
            "see the skill's references/setup.md."
        )


def run(args: list[str]) -> None:
    """Run a command, raising DigestError with its stderr on failure."""
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip()
        raise DigestError(f"{args[0]} failed: {detail}")


def probe(path: Path) -> dict:
    """Return ffprobe's JSON description of a media file."""
    if not path.is_file():
        raise DigestError(f"File does not exist: {path}")
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise DigestError(f"ffprobe could not read {path}: {result.stderr.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise DigestError(f"ffprobe returned unreadable output for {path}: {exc}") from None


def select_stream(probe_data: dict, codec_type: str) -> dict:
    """Return the first real stream of the given type, skipping cover art."""
    for stream in probe_data.get("streams", []):
        if stream.get("codec_type") != codec_type:
            continue
        if stream.get("disposition", {}).get("attached_pic"):
            continue
        return stream
    raise DigestError(f"Recording has no {codec_type} stream.")


def stream_gray_frames(
    video: Path, stream_index: int, filters: list[str], width: int, height: int
) -> Iterator["object"]:
    """Yield grayscale frames decoded through the given filter chain.

    Frames arrive as raw bytes on a pipe and are reshaped into numpy arrays.
    An incomplete final frame is an error, not a silent truncation.
    """
    import numpy as np

    command = [
        "ffmpeg", "-v", "error", "-nostdin", "-noautorotate", "-i", str(video),
        "-map", f"0:{stream_index}", "-an", "-vf", ",".join(filters),
        "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1",
    ]
    size = width * height
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors)
        try:
            while True:
                raw = bytearray()
                while len(raw) < size:
                    part = process.stdout.read(size - len(raw))
                    if not part:
                        break
                    raw.extend(part)
                if not raw:
                    break
                if len(raw) != size:
                    raise DigestError("ffmpeg produced an incomplete video frame.")
                yield np.frombuffer(bytes(raw), dtype=np.uint8).reshape(height, width)
            if process.wait():
                errors.seek(0)
                raise DigestError(errors.read().decode(errors="replace").strip())
        finally:
            if process.stdout is not None:
                process.stdout.close()
            if process.poll() is None:
                process.kill()
                process.wait()
```

- [ ] **Step 4: Run them and watch them pass**

Run: `python -m pytest tests/test_ffmpeg.py -v`
Expected: 6 passed. `test_run_raises_digest_error_with_the_stderr_text` needs ffmpeg on PATH; if it is missing, that is a real environment problem — install ffmpeg rather than skipping the test.

- [ ] **Step 5: Lint and commit**

```bash
ruff check . && ruff format --check .
git add src/meeting_digest/ffmpeg.py tests/test_ffmpeg.py
git commit -m "feat: add ffmpeg module as the single subprocess boundary"
```

**BATCH B CHECKPOINT — stop for review.**

---

# Batch C — Pipeline modules

### Task 6: `audio.py`

**Files:**
- Create: `src/meeting_digest/audio.py`
- Test: `tests/test_audio.py`
- Reference: `skills/meeting-digest/scripts/extract_audio.py` (deleted in Task 12)

**Interfaces:**
- Consumes: `DigestError`, `ffmpeg.probe/select_stream/run`, `timeline.stream_offset`.
- Produces:
  - `build_filters(offset: float) -> list[str]`
  - `extract_audio(video: Path, output: Path) -> Path`

- [ ] **Step 1: Write the failing tests**

`build_filters` is the logic worth testing — it is the part that keeps transcript times aligned to the video.

```python
import pytest

from meeting_digest.audio import build_filters


def test_aligned_audio_only_resets_the_timeline():
    assert build_filters(0.0) == ["asetpts=PTS-STARTPTS"]


def test_late_audio_is_padded_with_silence():
    assert build_filters(0.5) == ["asetpts=PTS-STARTPTS", "adelay=500:all=1"]


def test_padding_is_rounded_to_whole_milliseconds():
    assert build_filters(0.1234) == ["asetpts=PTS-STARTPTS", "adelay=123:all=1"]


def test_early_audio_is_trimmed_then_reset():
    assert build_filters(-0.25) == [
        "asetpts=PTS-STARTPTS",
        "atrim=start=0.25",
        "asetpts=PTS-STARTPTS",
    ]
```

- [ ] **Step 2: Run them and watch them fail**

Run: `python -m pytest tests/test_audio.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'meeting_digest.audio'`

- [ ] **Step 3: Implement**

```python
"""Extract meeting audio while preserving its position on the video timeline."""
from __future__ import annotations

from pathlib import Path

from meeting_digest.errors import DigestError
from meeting_digest.ffmpeg import probe, run, select_stream
from meeting_digest.timeline import stream_offset


def build_filters(offset: float) -> list[str]:
    """Return the ffmpeg audio filter chain for a given stream offset.

    Audio that starts late is padded with silence; audio that starts early is
    trimmed. Either way the result begins at the video's zero, so transcript
    timestamps line up with extracted frames.
    """
    filters = ["asetpts=PTS-STARTPTS"]
    if offset > 0:
        filters.append(f"adelay={round(offset * 1000)}:all=1")
    elif offset < 0:
        filters.extend([f"atrim=start={-offset}", "asetpts=PTS-STARTPTS"])
    return filters


def extract_audio(video: Path, output: Path) -> Path:
    """Write mono 16 kHz PCM audio, offset-corrected to the video timeline."""
    if output.exists():
        raise DigestError(f"Output already exists; choose a new path: {output}")
    data = probe(video)
    stream = select_stream(data, "audio")
    filters = build_filters(stream_offset(data, stream, clamp=False))
    output.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-v", "error", "-nostdin", "-n", "-i", str(video),
        "-map", "0:a:0", "-vn", "-af", ",".join(filters),
        "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(output),
    ])
    return output
```

- [ ] **Step 4: Run them and watch them pass**

Run: `python -m pytest tests/test_audio.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/meeting_digest/audio.py tests/test_audio.py
git commit -m "feat: port audio extraction with testable offset filter construction"
```

---

### Task 7: `frames.py`

The algorithm moves unchanged from `scripts/select_frames.py`. The only difference: `changed()` and `Selector` take a settings object instead of an argparse namespace, and numpy/cv2 are imported normally rather than through `global`.

**Files:**
- Create: `src/meeting_digest/frames.py`
- Test: `tests/test_frames.py`

**Interfaces:**
- Consumes: `DigestError`, `ffmpeg.stream_gray_frames`, `timeline.stream_offset/container_duration`.
- Produces:
  - `@dataclass(frozen=True) Thresholds(pixel_threshold=20.0, change_ratio=0.015, tile_ratio=0.12)`
  - `@dataclass(frozen=True) ScanSettings(sample_fps=2.0, stable_seconds=1.0, motion_interval=5.0, max_gap=30.0, thresholds=Thresholds())`
  - `changed(a, b, thresholds) -> bool`
  - `class Selector(settings)` with `.consider(t, frame) -> dict | None`, `.selected`, `.onset`
  - `build_scan_filters(stream, crop, sample_fps) -> tuple[list[str], int, int]`
  - `scan(video, stream, offset, settings, crop) -> tuple[list[dict], int]`

- [ ] **Step 1: Write the failing tests**

```python
import numpy as np
import pytest

from meeting_digest.errors import DigestError
from meeting_digest.frames import (
    ScanSettings,
    Selector,
    Thresholds,
    build_scan_filters,
    changed,
)

SIZE = (64, 64)


def blank(value=0):
    return np.full(SIZE, value, dtype=np.uint8)


def test_identical_frames_are_unchanged():
    assert changed(blank(), blank(), Thresholds()) is False


def test_a_small_bright_block_trips_the_tile_ratio():
    # A 64x64 frame splits into 8x8 tiles of 8x8 pixels each, so an 8x8 block
    # fills exactly one tile: that tile's mean is 1.0, far past tile_ratio,
    # while the overall changed area is only 1.6%.
    a, b = blank(), blank()
    b[0:8, 0:8] = 255
    assert changed(a, b, Thresholds()) is True


def test_diffuse_noise_below_the_pixel_threshold_is_ignored():
    a, b = blank(100), blank(110)  # 10 < pixel_threshold of 20
    assert changed(a, b, Thresholds()) is False


def test_a_full_frame_change_is_detected():
    assert changed(blank(0), blank(255), Thresholds()) is True


def test_the_first_frame_is_always_selected():
    selector = Selector(ScanSettings())
    result = selector.consider(0.0, blank())
    assert result["reason"] == "initial"
    assert result["timestamp"] == 0.0


def test_a_settled_change_is_selected_after_the_stability_window():
    settings = ScanSettings(sample_fps=2.0, stable_seconds=1.0)
    selector = Selector(settings)
    selector.consider(0.0, blank(0))
    # Change appears; motion is still happening, so it is not selected yet.
    assert selector.consider(0.5, blank(255)) is None
    # Screen is now static; after stable_seconds have passed it settles.
    assert selector.consider(1.0, blank(255)) is None
    result = selector.consider(1.5, blank(255))
    assert result["reason"] == "settled_change"


def test_coverage_fires_when_nothing_changes_for_max_gap():
    settings = ScanSettings(max_gap=2.0)
    selector = Selector(settings)
    selector.consider(0.0, blank())
    assert selector.consider(1.0, blank()) is None
    assert selector.consider(2.0, blank())["reason"] == "coverage"


def test_build_scan_filters_downscales_to_640_wide():
    stream = {"width": 1920, "height": 1080}
    filters, width, height = build_scan_filters(stream, None, 2.0)
    assert (width, height) == (640, 360)
    assert "fps=2.0:round=up" in filters
    assert "scale=640:360" in filters
    assert filters[-1] == "format=gray"


def test_build_scan_filters_applies_a_crop():
    stream = {"width": 1920, "height": 1080}
    filters, width, height = build_scan_filters(stream, (100, 50, 800, 600), 2.0)
    assert "crop=800:600:100:50" in filters
    assert (width, height) == (640, 480)


def test_build_scan_filters_rejects_a_crop_outside_the_frame():
    with pytest.raises(DigestError, match="outside the video"):
        build_scan_filters({"width": 640, "height": 480}, (600, 0, 100, 100), 2.0)


def test_build_scan_filters_rejects_a_tiny_crop():
    with pytest.raises(DigestError, match="outside the video|too small"):
        build_scan_filters({"width": 640, "height": 480}, (0, 0, 4, 4), 2.0)
```

- [ ] **Step 2: Run them and watch them fail**

Run: `python -m pytest tests/test_frames.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'meeting_digest.frames'`

- [ ] **Step 3: Implement**

```python
"""Local screenshot candidate selection. No vision model is involved.

The comparison runs on small grayscale samples; selected timestamps are later
re-extracted at full resolution from the source file.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from meeting_digest.errors import DigestError
from meeting_digest.ffmpeg import stream_gray_frames

SAMPLE_WIDTH = 640
TILE_GRID = 8


@dataclass(frozen=True)
class Thresholds:
    """How much a sample must differ before it counts as a change."""

    pixel_threshold: float = 20.0
    change_ratio: float = 0.015
    tile_ratio: float = 0.12


@dataclass(frozen=True)
class ScanSettings:
    """Sampling cadence and the rules that turn changes into candidates."""

    sample_fps: float = 2.0
    stable_seconds: float = 1.0
    motion_interval: float = 5.0
    max_gap: float = 30.0
    thresholds: Thresholds = field(default_factory=Thresholds)


def changed(a, b, thresholds: Thresholds) -> bool:
    """Whether two samples differ enough to matter.

    Compares both the overall changed area and the worst 8x8 tile, so a small
    localized edit — a line added to a slide — is not averaged away.
    """
    mask = cv2.absdiff(a, b) > thresholds.pixel_threshold
    overall = float(mask.mean())
    tiles = [
        float(tile.mean())
        for row in np.array_split(mask, TILE_GRID, axis=0)
        for tile in np.array_split(row, TILE_GRID, axis=1)
    ]
    return overall >= thresholds.change_ratio or max(tiles) >= thresholds.tile_ratio


class Selector:
    """Decides which sampled frames become screenshot candidates."""

    def __init__(self, settings: ScanSettings):
        self.settings = settings
        self.previous = self.selected = None
        self.selected_at = 0.0
        self.last_motion = 0.0
        self.onset = None

    def consider(self, t: float, frame) -> dict | None:
        settings = self.settings
        reason = None
        if self.previous is None:
            reason = "initial"
        else:
            moving = changed(frame, self.previous, settings.thresholds)
            different = changed(frame, self.selected, settings.thresholds)
            if moving:
                self.last_motion = t
            if different and self.onset is None:
                self.onset = t
            if not different:
                self.onset = None
            if different and t - self.last_motion >= settings.stable_seconds:
                reason = "settled_change"
            elif different and t - self.selected_at >= settings.motion_interval:
                reason = "motion_fallback"
            elif t - self.selected_at >= settings.max_gap:
                reason = "coverage"
        self.previous = frame.copy()
        if reason:
            result = {
                "timestamp": round(t, 6),
                "reason": reason,
                "approximate_change_start": self.onset,
            }
            self.selected, self.selected_at = frame.copy(), t
            self.onset = None
            return result
        return None


def build_scan_filters(
    stream: dict, crop: tuple[int, int, int, int] | None, sample_fps: float
) -> tuple[list[str], int, int]:
    """Build the sampling filter chain and the resulting sample dimensions."""
    width, height = stream["width"], stream["height"]
    filters = ["setpts=PTS-STARTPTS"]
    if crop:
        x, y, width, height = crop
        if (
            x < 0
            or y < 0
            or width < 8
            or height < 8
            or x + width > stream["width"]
            or y + height > stream["height"]
        ):
            raise DigestError("Crop is outside the video dimensions or too small.")
        filters.append(f"crop={width}:{height}:{x}:{y}")
    out_width = min(SAMPLE_WIDTH, width)
    out_height = max(8, round(height * out_width / width))
    filters.extend([
        f"fps={sample_fps}:round=up",
        f"scale={out_width}:{out_height}",
        "format=gray",
    ])
    return filters, out_width, out_height


def scan(
    video: Path,
    stream: dict,
    offset: float,
    settings: ScanSettings,
    crop: tuple[int, int, int, int] | None = None,
) -> tuple[list[dict], int]:
    """Sample the video locally and return candidate timestamps plus sample count."""
    filters, width, height = build_scan_filters(stream, crop, settings.sample_fps)
    selector = Selector(settings)
    selections: list[dict] = []
    index = 0
    last = None
    for frame in stream_gray_frames(video, stream["index"], filters, width, height):
        frame = cv2.GaussianBlur(frame, (3, 3), 0)
        t = offset + index / settings.sample_fps
        last = (t, frame)
        choice = selector.consider(t, frame)
        if choice:
            selections.append(choice)
        index += 1
    if last and selector.selected is not None and changed(
        last[1], selector.selected, settings.thresholds
    ):
        selections.append({
            "timestamp": round(last[0], 6),
            "reason": "final_change",
            "approximate_change_start": selector.onset,
        })
    return selections, index
```

- [ ] **Step 4: Run them and watch them pass**

Run: `python -m pytest tests/test_frames.py -v`
Expected: 11 passed. If `test_a_small_bright_block_trips_the_tile_ratio` fails, check the block size against `TILE_GRID` — a 64x64 frame has 8x8 tiles, so an 8x8 block fills exactly one tile and gives it a mean of 1.0, well past `tile_ratio`.

- [ ] **Step 5: Commit**

```bash
git add src/meeting_digest/frames.py tests/test_frames.py
git commit -m "feat: port frame selection with explicit settings dataclasses"
```

---

### Task 8: `labeling.py`

Moves nearly verbatim from `scripts/label_speakers.py:12-66`, minus its local `stamp()`.

**Files:**
- Create: `src/meeting_digest/labeling.py`
- Test: `tests/test_labeling.py`

**Interfaces:**
- Consumes: `DigestError`.
- Produces:
  - `validate_interval(row: dict) -> None`
  - `speaker_for(word: dict, turns: list[dict]) -> str | None`
  - `label(raw: dict, diarization: dict) -> dict`

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from meeting_digest.errors import DigestError
from meeting_digest.labeling import label, speaker_for, validate_interval


def turn(start, end, speaker):
    return {"start": start, "end": end, "source_speaker": speaker}


def word(start, end, text=" hi"):
    return {"start": start, "end": end, "text": text}


def test_a_word_inside_one_turn_gets_that_speaker():
    assert speaker_for(word(1.0, 1.5), [turn(0.0, 3.0, "SPEAKER_00")]) == "SPEAKER_00"


def test_a_word_with_no_overlapping_turn_is_unattributed():
    assert speaker_for(word(5.0, 5.5), [turn(0.0, 3.0, "SPEAKER_00")]) is None


def test_a_word_split_evenly_between_two_speakers_is_unattributed():
    turns = [turn(0.0, 1.0, "SPEAKER_00"), turn(1.0, 2.0, "SPEAKER_01")]
    assert speaker_for(word(0.5, 1.5), turns) is None


def test_a_word_barely_touching_a_turn_is_unattributed():
    # 0.1s of a 1.0s word overlaps, which is under the 50% floor.
    assert speaker_for(word(0.0, 1.0), [turn(0.9, 3.0, "SPEAKER_00")]) is None


def test_a_clear_majority_wins_over_a_brief_second_speaker():
    turns = [turn(0.0, 0.95, "SPEAKER_00"), turn(0.95, 2.0, "SPEAKER_01")]
    assert speaker_for(word(0.0, 1.0), turns) == "SPEAKER_00"


def test_validate_interval_rejects_a_negative_start():
    with pytest.raises(DigestError, match="interval"):
        validate_interval({"start": -1.0, "end": 1.0})


def test_validate_interval_rejects_a_reversed_interval():
    with pytest.raises(DigestError, match="interval"):
        validate_interval({"start": 2.0, "end": 1.0})


def test_validate_interval_rejects_a_non_numeric_value():
    with pytest.raises(DigestError, match="interval"):
        validate_interval({"start": "0", "end": 1.0})


RAW = {
    "source": "/tmp/audio.wav",
    "language": "en",
    "backend": "faster-whisper/small",
    "segments": [
        {
            "start": 0.0,
            "end": 2.0,
            "text": "hello there",
            "words": [word(0.0, 0.5, " hello"), word(0.6, 1.0, " there")],
        },
        {
            "start": 3.0,
            "end": 4.0,
            "text": "goodbye",
            "words": [word(3.0, 3.5, " goodbye")],
        },
    ],
}
DIARIZATION = {
    "source": "/tmp/audio.wav",
    "backend": "pyannote/speaker-diarization-community-1",
    "turns": [turn(0.0, 2.0, "SPEAKER_07"), turn(2.5, 4.0, "SPEAKER_03")],
}


def test_label_numbers_speakers_by_first_occurrence():
    result = label(RAW, DIARIZATION)
    assert result["speakers"] == {"SPEAKER_07": "Speaker 1", "SPEAKER_03": "Speaker 2"}


def test_label_merges_adjacent_words_from_the_same_speaker():
    segments = label(RAW, DIARIZATION)["segments"]
    assert len(segments) == 2
    assert segments[0]["speaker"] == "Speaker 1"
    assert segments[0]["text"] == "hello there"
    assert segments[1]["speaker"] == "Speaker 2"


def test_label_requires_word_timestamps():
    raw = {**RAW, "segments": [{"start": 0.0, "end": 1.0, "text": "hi", "words": []}]}
    with pytest.raises(DigestError, match="Word timestamps"):
        label(raw, DIARIZATION)
```

- [ ] **Step 2: Run them and watch them fail**

Run: `python -m pytest tests/test_labeling.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'meeting_digest.labeling'`

- [ ] **Step 3: Implement**

Copy `speaker_for` and `label` from `scripts/label_speakers.py:22-66` unchanged, and convert `validate_interval` to raise `DigestError`.

```python
"""Align word-timed transcript text with diarization turns.

Words that cannot be attributed confidently stay unattributed rather than
being guessed at — a wrong speaker label is worse than a missing one.
"""
from __future__ import annotations

import math

from meeting_digest.errors import DigestError

MERGE_GAP_SECONDS = 1.5
MAJORITY = 0.5


def validate_interval(row: dict) -> None:
    start, end = row.get("start"), row.get("end")
    numeric = all(isinstance(x, (int, float)) and math.isfinite(x) for x in (start, end))
    if not numeric or start < 0 or end < start:
        raise DigestError(f"Invalid time interval: {row}")


def speaker_for(word: dict, turns: list[dict]) -> str | None:
    """Return the diarization speaker that clearly owns this word, or None.

    None means either no overlap, less than half the word covered, or two
    speakers too close to separate.
    """
    overlap: dict[str, float] = {}
    duration = max(word["end"] - word["start"], 0.001)
    for turn in turns:
        shared = max(0.0, min(word["end"], turn["end"]) - max(word["start"], turn["start"]))
        if shared:
            key = turn["source_speaker"]
            overlap[key] = overlap.get(key, 0.0) + shared
    if not overlap:
        return None
    ranked = sorted(overlap.items(), key=lambda item: item[1], reverse=True)
    if ranked[0][1] < MAJORITY * duration:
        return None
    if len(ranked) > 1 and ranked[1][1] >= MAJORITY * ranked[0][1]:
        return None
    return ranked[0][0]


def label(raw: dict, diarization: dict) -> dict:
    """Combine a raw transcript and speaker turns into a labeled transcript."""
    turns = diarization["turns"]
    for turn in turns:
        validate_interval(turn)
    turns = sorted(turns, key=lambda t: (t["start"], t["end"]))

    words = []
    for segment in raw["segments"]:
        validate_interval(segment)
        if not segment.get("words"):
            raise DigestError("Word timestamps are required for reliable speaker alignment.")
        for word in segment["words"]:
            validate_interval(word)
            words.append(word)
    words.sort(key=lambda w: (w["start"], w["end"]))

    names: dict[str, str] = {}
    result: list[dict] = []
    for word in words:
        source = speaker_for(word, turns)
        if source is not None and source not in names:
            names[source] = f"Speaker {len(names) + 1}"
        speaker = names.get(source)
        mergeable = (
            result
            and result[-1]["speaker"] == speaker
            and word["start"] - result[-1]["end"] <= MERGE_GAP_SECONDS
        )
        if mergeable:
            result[-1]["end"] = max(result[-1]["end"], word["end"])
            result[-1]["text"] += word["text"]
        else:
            result.append({
                "start": word["start"],
                "end": word["end"],
                "speaker": speaker,
                "text": word["text"].lstrip(),
            })
    return {
        "source": raw["source"],
        "language": raw.get("language"),
        "backend": f'{raw["backend"]} + {diarization["backend"]}',
        "speakers": names,
        "segments": result,
        "note": "Null speaker means no reliable match or overlapping speakers.",
    }
```

- [ ] **Step 4: Run them and watch them pass**

Run: `python -m pytest tests/test_labeling.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add src/meeting_digest/labeling.py tests/test_labeling.py
git commit -m "feat: port speaker labeling with DigestError validation"
```

---

### Task 9: `transcribe.py` and `diarize.py`

Thin wrappers. The model libraries are faked in tests — this suite checks that *our* code handles their output, not that the models are accurate.

**Files:**
- Create: `src/meeting_digest/transcribe.py`, `src/meeting_digest/diarize.py`
- Test: `tests/test_transcribe.py`, `tests/test_diarize.py`

**Interfaces:**
- Consumes: `DigestError`, `timeline.stamp`.
- Produces:
  - `transcribe.transcribe(audio, model, language, device, compute_type) -> dict`
  - `transcribe.render_markdown(segments: list[dict]) -> str`
  - `diarize.load_pcm16_mono(path: Path) -> dict`
  - `diarize.diarize(audio, model, min_speakers, max_speakers) -> dict`

- [ ] **Step 1: Write the failing tests**

`tests/test_transcribe.py`:

```python
from meeting_digest.transcribe import render_markdown, segments_from_model


class FakeWord:
    def __init__(self, start, end, text):
        self.start, self.end, self.word = start, end, text


class FakeSegment:
    def __init__(self, start, end, text, words):
        self.start, self.end, self.text, self.words = start, end, text, words


def test_segments_from_model_keeps_word_timings():
    raw = [FakeSegment(0.0, 1.0, " hello ", [FakeWord(0.0, 0.5, " hello")])]
    rows = segments_from_model(raw)
    assert rows == [
        {
            "start": 0.0,
            "end": 1.0,
            "text": "hello",
            "words": [{"start": 0.0, "end": 0.5, "text": " hello"}],
        }
    ]


def test_segments_from_model_drops_words_without_timings():
    raw = [FakeSegment(0.0, 1.0, "hi", [FakeWord(None, 0.5, " hi"), FakeWord(0.6, 1.0, " you")])]
    assert len(segments_from_model(raw)[0]["words"]) == 1


def test_segments_from_model_tolerates_a_segment_with_no_words():
    raw = [FakeSegment(0.0, 1.0, "hi", None)]
    assert segments_from_model(raw)[0]["words"] == []


def test_render_markdown_uses_readable_timestamps():
    rows = [{"start": 0.0, "end": 1.5, "text": "hello"}]
    assert render_markdown(rows) == "# Transcript\n\n[00:00:00.000–00:00:01.500] hello"
```

`tests/test_diarize.py`:

```python
import wave

import numpy as np
import pytest

from meeting_digest.diarize import load_pcm16_mono, turns_from_annotation
from meeting_digest.errors import DigestError


def write_wav(path, channels=1, width=2, rate=16000, frames=b"\x00\x00" * 100):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(rate)
        wav.writeframes(frames)
    return path


def test_load_pcm16_mono_returns_a_waveform_and_rate(tmp_path):
    result = load_pcm16_mono(write_wav(tmp_path / "a.wav"))
    assert result["sample_rate"] == 16000
    assert result["waveform"].shape == (1, 100)


def test_load_pcm16_mono_normalizes_to_minus_one_to_one(tmp_path):
    frames = np.array([32767, -32768, 0], dtype="<i2").tobytes()
    result = load_pcm16_mono(write_wav(tmp_path / "a.wav", frames=frames))
    values = result["waveform"][0].tolist()
    assert values[0] == pytest.approx(0.99997, abs=1e-4)
    assert values[1] == pytest.approx(-1.0)
    assert values[2] == 0.0


def test_load_pcm16_mono_rejects_stereo(tmp_path):
    path = write_wav(tmp_path / "a.wav", channels=2, frames=b"\x00\x00\x00\x00" * 10)
    with pytest.raises(DigestError, match="mono"):
        load_pcm16_mono(path)


def test_turns_from_annotation_sorts_and_names_speakers():
    annotation = [
        (types.SimpleNamespace(start=2.0, end=3.0), "SPEAKER_01"),
        (types.SimpleNamespace(start=0.0, end=1.0), "SPEAKER_00"),
    ]
    turns = turns_from_annotation(annotation)
    assert [t["start"] for t in turns] == [0.0, 2.0]
    assert turns[0]["source_speaker"] == "SPEAKER_00"


def test_turns_from_annotation_detects_overlap():
    annotation = [
        (types.SimpleNamespace(start=0.0, end=2.0), "SPEAKER_00"),
        (types.SimpleNamespace(start=1.0, end=3.0), "SPEAKER_01"),
    ]
    turns = turns_from_annotation(annotation)
    assert any(x["end"] > y["start"] for x, y in zip(turns, turns[1:]))
```

Add `import types` at the top of `tests/test_diarize.py`.

- [ ] **Step 2: Run them and watch them fail**

Run: `python -m pytest tests/test_transcribe.py tests/test_diarize.py -v`
Expected: FAIL — both modules missing.

- [ ] **Step 3: Implement `transcribe.py`**

```python
"""Word-timed transcription via faster-whisper."""
from __future__ import annotations

from pathlib import Path

from meeting_digest.errors import DigestError
from meeting_digest.timeline import stamp


def segments_from_model(model_segments) -> list[dict]:
    """Convert faster-whisper segments into plain dictionaries.

    Words without both timings are dropped: speaker alignment needs real
    intervals, and a word with a missing bound cannot be placed.
    """
    return [
        {
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip(),
            "words": [
                {"start": word.start, "end": word.end, "text": word.word}
                for word in (segment.words or [])
                if word.start is not None and word.end is not None
            ],
        }
        for segment in model_segments
    ]


def render_markdown(segments: list[dict]) -> str:
    body = "\n\n".join(
        f'[{stamp(s["start"])}–{stamp(s["end"])}] {s["text"]}' for s in segments
    )
    return "# Transcript\n\n" + body


def transcribe(
    audio: Path,
    model: str = "small",
    language: str | None = None,
    device: str = "cpu",
    compute_type: str = "int8",
) -> dict:
    """Return a raw transcript with word-level timings."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise DigestError(
            "faster-whisper is not installed in this Python environment. "
            "Reinstall the package: pip install meeting-digest"
        ) from None
    whisper = WhisperModel(model, device=device, compute_type=compute_type)
    model_segments, info = whisper.transcribe(str(audio), language=language, word_timestamps=True)
    return {
        "source": str(audio.resolve()),
        "language": info.language,
        "backend": f"faster-whisper/{model}",
        "segments": segments_from_model(model_segments),
    }
```

- [ ] **Step 4: Implement `diarize.py`**

```python
"""Speaker turn detection via pyannote."""
from __future__ import annotations

import wave
from pathlib import Path

from meeting_digest.errors import DigestError

DEFAULT_MODEL = "pyannote/speaker-diarization-community-1"


def load_pcm16_mono(path: Path) -> dict:
    """Read the WAV written by extract-audio directly into memory.

    Passing the waveform in avoids TorchCodec decoding and its separate FFmpeg
    compatibility requirements.
    """
    import numpy as np
    import torch

    with wave.open(str(path), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getcomptype() != "NONE":
            raise DigestError(
                "Expected uncompressed mono 16-bit PCM WAV from `meeting-digest extract-audio`."
            )
        sample_rate = wav.getframerate()
        samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
    waveform = torch.from_numpy(samples.astype(np.float32) / 32768.0).unsqueeze(0)
    return {"waveform": waveform, "sample_rate": sample_rate}


def turns_from_annotation(annotation) -> list[dict]:
    """Convert pyannote's (segment, speaker) pairs into sorted plain rows."""
    turns = [
        {"start": segment.start, "end": segment.end, "source_speaker": str(speaker)}
        for segment, speaker in annotation
    ]
    turns.sort(key=lambda row: (row["start"], row["end"]))
    return turns


def diarize(
    audio: Path,
    model: str = DEFAULT_MODEL,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
) -> dict:
    """Return speaker turns for an audio file."""
    try:
        import torch
        from pyannote.audio import Pipeline
    except ImportError:
        raise DigestError(
            "pyannote.audio is not installed in this Python environment. "
            "Reinstall the package: pip install meeting-digest"
        ) from None
    try:
        pipeline = Pipeline.from_pretrained(model)
    except Exception as exc:
        raise DigestError(
            f"Could not load the pyannote model: {exc}. Accepting the model terms on "
            "Hugging Face and running `hf auth login` is required; see the skill's "
            "references/setup.md."
        ) from None
    if torch.cuda.is_available():
        pipeline.to(torch.device("cuda"))
    kwargs = {
        key: value
        for key, value in (("min_speakers", min_speakers), ("max_speakers", max_speakers))
        if value is not None
    }
    output = pipeline(load_pcm16_mono(audio), **kwargs)
    turns = turns_from_annotation(output.speaker_diarization)
    return {
        "source": str(audio.resolve()),
        "backend": model,
        "min_speakers": min_speakers,
        "max_speakers": max_speakers,
        "turns": turns,
        "has_overlaps": any(x["end"] > y["start"] for x, y in zip(turns, turns[1:])),
    }
```

- [ ] **Step 5: Run them and watch them pass**

Run: `python -m pytest tests/test_transcribe.py tests/test_diarize.py -v`
Expected: 9 passed.

- [ ] **Step 6: Commit**

```bash
git add src/meeting_digest/transcribe.py src/meeting_digest/diarize.py tests/test_transcribe.py tests/test_diarize.py
git commit -m "feat: port transcription and diarization wrappers"
```

---

### Task 10: `manifest.py`

One definition of each artifact format, plus the validation the `validate` command exposes.

**Files:**
- Create: `src/meeting_digest/manifest.py`
- Test: `tests/test_manifest.py`

**Interfaces:**
- Consumes: `DigestError`.
- Produces:
  - `write_json(path: Path, data: dict, *, ensure_ascii: bool = True) -> Path`
  - `build_frames_manifest(source, duration, sampled, settings, choices) -> dict`
  - `validate_meeting(directory: Path) -> list[str]` — returns problem strings, empty when valid
  - `mark_inspected(directory: Path, frame_ids: list[str]) -> int`

- [ ] **Step 1: Write the failing tests**

```python
import json

import pytest

from meeting_digest.errors import DigestError
from meeting_digest.manifest import (
    build_frames_manifest,
    mark_inspected,
    validate_meeting,
    write_json,
)


def make_meeting(tmp_path, frames=None):
    directory = tmp_path / "meeting"
    (directory / "frames").mkdir(parents=True)
    frames = frames if frames is not None else [
        {
            "id": "frame-00001",
            "timestamp": 0.0,
            "reason": "initial",
            "approximate_change_start": None,
            "path": "frames/frame-00001-0.000s.png",
            "inspected": False,
        }
    ]
    for frame in frames:
        (directory / frame["path"]).write_bytes(b"\x89PNG\r\n\x1a\n")
    write_json(
        directory / "frames.json",
        {
            "source": "/tmp/a.mp4",
            "duration": 10.0,
            "timestamp_basis": "seconds relative to container start",
            "sampled_frames": 20,
            "settings": {},
            "frames": frames,
        },
    )
    return directory


def test_write_json_creates_parents_and_writes_utf8(tmp_path):
    target = write_json(tmp_path / "a" / "b.json", {"text": "Grüße"}, ensure_ascii=False)
    assert json.loads(target.read_text(encoding="utf-8"))["text"] == "Grüße"


def test_build_frames_manifest_assigns_ids_and_paths():
    choices = [
        {"timestamp": 0.0, "reason": "initial", "approximate_change_start": None},
        {"timestamp": 1.25, "reason": "settled_change", "approximate_change_start": 1.0},
    ]
    manifest = build_frames_manifest("/tmp/a.mp4", 10.0, 20, {}, choices)
    assert manifest["frames"][0]["id"] == "frame-00001"
    assert manifest["frames"][1]["path"] == "frames/frame-00002-1.250s.png"
    assert manifest["frames"][1]["inspected"] is False


def test_validate_accepts_a_well_formed_meeting(tmp_path):
    assert validate_meeting(make_meeting(tmp_path)) == []


def test_validate_reports_a_missing_png(tmp_path):
    directory = make_meeting(tmp_path)
    (directory / "frames" / "frame-00001-0.000s.png").unlink()
    problems = validate_meeting(directory)
    assert any("frame-00001" in p for p in problems)


def test_validate_reports_a_negative_timestamp(tmp_path):
    directory = make_meeting(tmp_path)
    data = json.loads((directory / "frames.json").read_text(encoding="utf-8"))
    data["frames"][0]["timestamp"] = -1.0
    write_json(directory / "frames.json", data)
    assert any("timestamp" in p for p in validate_meeting(directory))


def test_validate_reports_duplicate_frame_ids(tmp_path):
    frames = [
        {
            "id": "frame-00001",
            "timestamp": 0.0,
            "reason": "initial",
            "approximate_change_start": None,
            "path": "frames/frame-00001-0.000s.png",
            "inspected": False,
        },
        {
            "id": "frame-00001",
            "timestamp": 1.0,
            "reason": "coverage",
            "approximate_change_start": None,
            "path": "frames/frame-00002-1.000s.png",
            "inspected": False,
        },
    ]
    assert any("duplicate" in p.lower() for p in validate_meeting(make_meeting(tmp_path, frames)))


def test_validate_reports_a_missing_directory(tmp_path):
    assert any("does not exist" in p for p in validate_meeting(tmp_path / "nope"))


def test_validate_reports_mismatched_transcript_sources(tmp_path):
    directory = make_meeting(tmp_path)
    write_json(directory / "transcript.json", {"source": "/tmp/a.wav", "segments": []})
    write_json(directory / "speaker_turns.json", {"source": "/tmp/b.wav", "turns": []})
    assert any("same audio" in p for p in validate_meeting(directory))


def test_mark_inspected_sets_the_flag(tmp_path):
    directory = make_meeting(tmp_path)
    assert mark_inspected(directory, ["frame-00001"]) == 1
    data = json.loads((directory / "frames.json").read_text(encoding="utf-8"))
    assert data["frames"][0]["inspected"] is True


def test_mark_inspected_rejects_an_unknown_id(tmp_path):
    with pytest.raises(DigestError, match="frame-99999"):
        mark_inspected(make_meeting(tmp_path), ["frame-99999"])
```

- [ ] **Step 2: Run them and watch them fail**

Run: `python -m pytest tests/test_manifest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'meeting_digest.manifest'`

- [ ] **Step 3: Implement**

```python
"""The artifact formats both skills depend on: writing and checking them.

The contract these functions enforce is documented for skill authors in
skills/meeting-digest/references/artifacts.md.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from meeting_digest.errors import DigestError

TIMESTAMP_BASIS = "seconds relative to container start; sampled times approximate"


def write_json(path: Path, data: dict, *, ensure_ascii: bool = True) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=ensure_ascii), encoding="utf-8")
    return path


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DigestError(f"{path} is not valid JSON: {exc}") from None


def build_frames_manifest(
    source: str, duration: float, sampled: int, settings: dict, choices: list[dict]
) -> dict:
    """Assign ids and relative paths to selected timestamps."""
    frames = []
    for position, choice in enumerate(choices, 1):
        name = f'frame-{position:05d}-{choice["timestamp"]:.3f}s.png'
        frames.append({
            **choice,
            "id": f"frame-{position:05d}",
            "path": f"frames/{name}",
            "inspected": False,
        })
    return {
        "source": source,
        "duration": duration,
        "timestamp_basis": TIMESTAMP_BASIS,
        "sampled_frames": sampled,
        "settings": settings,
        "frames": frames,
    }


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def _check_frames(directory: Path, problems: list[str]) -> None:
    path = directory / "frames.json"
    if not path.is_file():
        return
    data = read_json(path)
    for key in ("source", "duration", "frames"):
        if key not in data:
            problems.append(f"frames.json is missing the required key {key!r}")
    seen: set[str] = set()
    for frame in data.get("frames", []):
        frame_id = frame.get("id", "<no id>")
        if frame_id in seen:
            problems.append(f"frames.json has a duplicate frame id: {frame_id}")
        seen.add(frame_id)
        if not _finite(frame.get("timestamp")) or frame["timestamp"] < 0:
            problems.append(f"{frame_id} has a non-finite or negative timestamp")
        relative = frame.get("path")
        if not relative:
            problems.append(f"{frame_id} has no path")
        elif not (directory / relative).is_file():
            problems.append(f"{frame_id} points at a missing image: {relative}")
        elif (directory / relative).stat().st_size == 0:
            problems.append(f"{frame_id} points at an empty image: {relative}")


def _check_intervals(path: Path, rows_key: str, problems: list[str]) -> None:
    if not path.is_file():
        return
    data = read_json(path)
    for row in data.get(rows_key, []):
        start, end = row.get("start"), row.get("end")
        if not _finite(start) or not _finite(end) or start < 0 or end < start:
            problems.append(f"{path.name} contains an invalid interval: {start} to {end}")
            break


def _check_sources_agree(directory: Path, problems: list[str]) -> None:
    transcript = directory / "transcript.json"
    turns = directory / "speaker_turns.json"
    if not (transcript.is_file() and turns.is_file()):
        return
    if read_json(transcript).get("source") != read_json(turns).get("source"):
        problems.append(
            "transcript.json and speaker_turns.json must come from the same audio file"
        )


def validate_meeting(directory: Path) -> list[str]:
    """Check a meeting directory against the artifact contract.

    Returns a list of problems; an empty list means the directory is valid.
    Missing optional artifacts are not problems — a meeting with only frames
    is a legitimate partial ingestion.
    """
    problems: list[str] = []
    if not directory.is_dir():
        return [f"Meeting directory does not exist: {directory}"]
    _check_frames(directory, problems)
    _check_intervals(directory / "transcript.json", "segments", problems)
    _check_intervals(directory / "speaker_turns.json", "turns", problems)
    _check_sources_agree(directory, problems)
    if not any((directory / name).exists() for name in ("frames.json", "transcript.json")):
        problems.append(
            f"{directory} contains no frames.json or transcript.json; nothing was ingested here"
        )
    return problems


def mark_inspected(directory: Path, frame_ids: list[str]) -> int:
    """Set `inspected` to true for the named frames. Returns how many changed."""
    path = directory / "frames.json"
    if not path.is_file():
        raise DigestError(f"No frames.json in {directory}")
    data = read_json(path)
    known = {frame.get("id") for frame in data.get("frames", [])}
    unknown = [frame_id for frame_id in frame_ids if frame_id not in known]
    if unknown:
        raise DigestError(f"Unknown frame ids: {', '.join(unknown)}")
    changed = 0
    for frame in data["frames"]:
        if frame["id"] in frame_ids and not frame.get("inspected"):
            frame["inspected"] = True
            changed += 1
    write_json(path, data)
    return changed
```

- [ ] **Step 4: Run them and watch them pass**

Run: `python -m pytest tests/test_manifest.py -v`
Expected: 10 passed.

- [ ] **Step 5: Run the whole suite and lint**

```bash
python -m pytest -v
ruff check . && ruff format --check .
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/meeting_digest/manifest.py tests/test_manifest.py
git commit -m "feat: add artifact manifest writing and validation"
```

**BATCH C CHECKPOINT — stop for review.**

---

# Batch D — Command line

### Task 11: Wire the existing commands into `cli.py`

**Files:**
- Modify: `src/meeting_digest/cli.py` (replace wholesale)
- Create: `src/meeting_digest/pipeline.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: every module from Batch B and C.
- Produces:
  - `cli.build_parser()` with subcommands `check`, `extract-audio`, `frames`, `transcribe`, `diarize`, `label`
  - `pipeline.select_frames(video, output, settings, crop, timestamps) -> Path`
  - `pipeline.write_transcript(audio, output, **options) -> Path`
  - `pipeline.write_speaker_turns(audio, output, **options) -> Path`
  - `pipeline.write_labeled_transcript(raw_path, turns_path, output) -> Path`

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from meeting_digest.cli import build_parser, main


def parse(argv):
    return build_parser().parse_args(argv)


def test_check_needs_no_arguments():
    assert parse(["check"]).command == "check"


def test_frames_defaults_match_the_original_script():
    args = parse(["frames", "a.mp4", "out"])
    assert args.sample_fps == 2
    assert args.stable_seconds == 1
    assert args.motion_interval == 5
    assert args.max_gap == 30
    assert args.pixel_threshold == 20
    assert args.change_ratio == pytest.approx(0.015)
    assert args.tile_ratio == pytest.approx(0.12)


def test_transcribe_defaults_match_the_original_script():
    args = parse(["transcribe", "a.wav", "out"])
    assert args.model == "small"
    assert args.language is None
    assert args.device == "cpu"
    assert args.compute_type == "int8"


def test_an_unknown_command_exits_two():
    with pytest.raises(SystemExit) as exc:
        parse(["nonsense"])
    assert exc.value.code == 2


def test_a_digest_error_is_printed_without_a_traceback(capsys):
    code = main(["extract-audio", "definitely-missing.mp4", "out/audio.wav"])
    assert code == 2
    assert capsys.readouterr().err.startswith("error: ")


def test_check_reports_every_dependency(capsys):
    assert main(["check"]) == 0
    out = capsys.readouterr().out
    for name in ("ffmpeg", "ffprobe", "numpy", "cv2"):
        assert name in out


def test_frames_rejects_a_non_positive_threshold(capsys):
    with pytest.raises(SystemExit):
        main(["frames", "a.mp4", "out", "--sample-fps", "0"])


def test_frames_rejects_a_ratio_above_one():
    with pytest.raises(SystemExit):
        main(["frames", "a.mp4", "out", "--change-ratio", "2"])


def test_frames_rejects_a_malformed_crop():
    with pytest.raises(SystemExit):
        main(["frames", "a.mp4", "out", "--crop", "1,2,3"])
```

- [ ] **Step 2: Run them and watch them fail**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL — the subcommands do not exist yet.

- [ ] **Step 3: Implement `pipeline.py`**

These are the orchestration bodies lifted out of the old `main()` functions.

```python
"""Each command's end-to-end work: read inputs, call modules, write artifacts."""
from __future__ import annotations

from pathlib import Path

from meeting_digest import diarize as diarize_module
from meeting_digest import transcribe as transcribe_module
from meeting_digest.errors import DigestError
from meeting_digest.ffmpeg import probe, run, select_stream
from meeting_digest.frames import ScanSettings, scan
from meeting_digest.labeling import label
from meeting_digest.manifest import build_frames_manifest, read_json, write_json
from meeting_digest.timeline import container_duration, stamp, stream_offset


def select_frames(
    video: Path,
    output: Path,
    settings: ScanSettings,
    crop: tuple[int, int, int, int] | None,
    timestamps: list[float] | None,
    settings_record: dict,
) -> Path:
    """Scan or extract at explicit times, then save full-resolution PNGs."""
    if (output / "frames.json").exists() or (output / "frames").exists():
        raise DigestError("Frame outputs already exist; use a fresh output directory.")
    data = probe(video)
    stream = select_stream(data, "video")
    offset = stream_offset(data, stream, clamp=True)
    duration = container_duration(data, stream)

    if timestamps is not None:
        out_of_range = [t for t in timestamps if t < offset or t >= duration]
        if out_of_range:
            raise DigestError(
                f"Timestamps outside the video timeline ({offset:.3f}–{duration:.3f}s): "
                + ", ".join(f"{t:g}" for t in out_of_range)
            )
        choices = [
            {"timestamp": t, "reason": "requested", "approximate_change_start": None}
            for t in timestamps
        ]
        sampled = 0
    else:
        choices, sampled = scan(video, stream, offset, settings, crop)

    if not choices:
        raise DigestError("No frames decoded.")

    manifest = build_frames_manifest(
        str(video.resolve()), duration, sampled, settings_record, choices
    )
    (output / "frames").mkdir(parents=True)
    for frame in manifest["frames"]:
        target = output / frame["path"]
        run([
            "ffmpeg", "-v", "error", "-nostdin", "-n", "-ss", str(frame["timestamp"]),
            "-noautorotate", "-i", str(video), "-map", f'0:{stream["index"]}',
            "-frames:v", "1", "-update", "1", str(target),
        ])
        if not target.is_file() or target.stat().st_size == 0:
            raise DigestError(
                f'No image produced at {frame["timestamp"]}; no complete manifest written.'
            )
    return write_json(output / "frames.json", manifest)


def write_transcript(audio: Path, output: Path, **options) -> Path:
    targets = [output / "transcript_raw.json", output / "transcript_raw.md"]
    if any(target.exists() for target in targets):
        raise DigestError("Transcript exists; choose a new output directory.")
    result = transcribe_module.transcribe(audio, **options)
    write_json(targets[0], result, ensure_ascii=False)
    targets[1].write_text(
        transcribe_module.render_markdown(result["segments"]), encoding="utf-8"
    )
    return targets[0]


def write_speaker_turns(audio: Path, output: Path, **options) -> Path:
    if output.exists():
        raise DigestError(f"Output already exists; choose a new path: {output}")
    return write_json(output, diarize_module.diarize(audio, **options))


def write_labeled_transcript(raw_path: Path, turns_path: Path, output: Path) -> Path:
    targets = [output / "transcript.json", output / "transcript.md"]
    if any(target.exists() for target in targets):
        raise DigestError("Labeled transcript already exists; choose a new output directory.")
    raw = read_json(raw_path)
    diarization = read_json(turns_path)
    if Path(raw["source"]).resolve() != Path(diarization["source"]).resolve():
        raise DigestError("Transcript and speaker turns come from different audio files.")
    result = label(raw, diarization)
    write_json(targets[0], result, ensure_ascii=False)
    body = "\n\n".join(
        f'[{stamp(s["start"])}–{stamp(s["end"])}] '
        f'{s["speaker"] or "Speaker uncertain"}: {s["text"]}'
        for s in result["segments"]
    )
    targets[1].write_text("# Transcript\n\n" + body, encoding="utf-8")
    return targets[0]
```

- [ ] **Step 4: Implement the full `cli.py`**

```python
"""Command-line front door. Parses arguments and dispatches to the modules."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from meeting_digest import __version__, pipeline
from meeting_digest.audio import extract_audio
from meeting_digest.diarize import DEFAULT_MODEL
from meeting_digest.errors import DigestError
from meeting_digest.ffmpeg import dependencies, require_dependencies
from meeting_digest.frames import ScanSettings, Thresholds

_SCAN_FLOATS = (
    "sample_fps",
    "stable_seconds",
    "motion_interval",
    "max_gap",
    "pixel_threshold",
    "change_ratio",
    "tile_ratio",
)


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meeting-digest",
        description="Turn recorded meetings into transcripts, screenshots, and notes.",
    )
    parser.add_argument("--version", action="version", version=f"meeting-digest {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    sub.add_parser("check", help="Report whether FFmpeg, ffprobe, numpy and cv2 are available")

    audio = sub.add_parser("extract-audio", help="Extract offset-corrected mono 16 kHz WAV")
    audio.add_argument("video", type=Path)
    audio.add_argument("output", type=Path)

    frames = sub.add_parser("frames", help="Select screenshot candidates locally")
    frames.add_argument("video", type=Path)
    frames.add_argument("output", type=Path)
    frames.add_argument("--sample-fps", type=float, default=2)
    frames.add_argument("--stable-seconds", type=float, default=1)
    frames.add_argument("--motion-interval", type=float, default=5)
    frames.add_argument("--max-gap", type=float, default=30)
    frames.add_argument("--pixel-threshold", type=float, default=20)
    frames.add_argument("--change-ratio", type=float, default=0.015)
    frames.add_argument("--tile-ratio", type=float, default=0.12)
    frames.add_argument("--crop", help="Comparison region in original pixels: x,y,width,height")
    frames.add_argument("--timestamps", help="Extract only these comma-separated times in seconds")

    transcribe = sub.add_parser("transcribe", help="Word-timed transcription")
    transcribe.add_argument("audio", type=Path)
    transcribe.add_argument("output", type=Path)
    transcribe.add_argument("--model", default="small")
    transcribe.add_argument("--language")
    transcribe.add_argument("--device", default="cpu")
    transcribe.add_argument("--compute-type", default="int8")

    diarize = sub.add_parser("diarize", help="Detect speaker turns")
    diarize.add_argument("audio", type=Path)
    diarize.add_argument("output", type=Path, help="Path to speaker_turns.json")
    diarize.add_argument("--model", default=DEFAULT_MODEL)
    diarize.add_argument("--min-speakers", type=_positive_int)
    diarize.add_argument("--max-speakers", type=_positive_int)

    label = sub.add_parser("label", help="Combine a raw transcript with speaker turns")
    label.add_argument("raw_transcript", type=Path)
    label.add_argument("speaker_turns", type=Path)
    label.add_argument("output", type=Path, help="Meeting directory for transcript.json/md")

    return parser


def _scan_settings(parser: argparse.ArgumentParser, args) -> tuple[ScanSettings, dict]:
    for key in _SCAN_FLOATS:
        value = getattr(args, key)
        if not math.isfinite(value) or value <= 0:
            parser.error(f'--{key.replace("_", "-")} must be positive and finite.')
    if args.change_ratio > 1 or args.tile_ratio > 1 or args.pixel_threshold > 255:
        parser.error("Ratios must be <= 1; pixel threshold must be <= 255.")
    settings = ScanSettings(
        sample_fps=args.sample_fps,
        stable_seconds=args.stable_seconds,
        motion_interval=args.motion_interval,
        max_gap=args.max_gap,
        thresholds=Thresholds(
            pixel_threshold=args.pixel_threshold,
            change_ratio=args.change_ratio,
            tile_ratio=args.tile_ratio,
        ),
    )
    record = {key: getattr(args, key) for key in _SCAN_FLOATS}
    record.update(crop=args.crop, timestamps=args.timestamps)
    return settings, record


def _parse_crop(parser: argparse.ArgumentParser, raw: str | None):
    if not raw:
        return None
    try:
        crop = tuple(int(part) for part in raw.split(","))
    except ValueError:
        parser.error("--crop must contain four integers.")
    if len(crop) != 4:
        parser.error("--crop must contain four integers.")
    return crop


def _parse_timestamps(parser: argparse.ArgumentParser, raw: str | None):
    if not raw:
        return None
    try:
        times = sorted({float(part) for part in raw.split(",")})
    except ValueError:
        parser.error("Timestamps must be numbers separated by commas.")
    if any(not math.isfinite(t) for t in times):
        parser.error("Timestamps must be finite numbers.")
    return times


def _run_command(parser: argparse.ArgumentParser, args) -> int:
    if args.command == "check":
        print(json.dumps(dependencies(), indent=2))
        return 0

    require_dependencies()

    if args.command == "extract-audio":
        print(extract_audio(args.video, args.output))
    elif args.command == "frames":
        settings, record = _scan_settings(parser, args)
        print(pipeline.select_frames(
            args.video,
            args.output,
            settings,
            _parse_crop(parser, args.crop),
            _parse_timestamps(parser, args.timestamps),
            record,
        ))
    elif args.command == "transcribe":
        print(pipeline.write_transcript(
            args.audio,
            args.output,
            model=args.model,
            language=args.language,
            device=args.device,
            compute_type=args.compute_type,
        ))
    elif args.command == "diarize":
        if args.min_speakers and args.max_speakers and args.min_speakers > args.max_speakers:
            parser.error("--min-speakers cannot exceed --max-speakers.")
        print(pipeline.write_speaker_turns(
            args.audio,
            args.output,
            model=args.model,
            min_speakers=args.min_speakers,
            max_speakers=args.max_speakers,
        ))
    elif args.command == "label":
        print(pipeline.write_labeled_transcript(
            args.raw_transcript, args.speaker_turns, args.output
        ))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1
    try:
        return _run_command(parser, args)
    except DigestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run them and watch them pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: 9 passed.

- [ ] **Step 6: Delete the old scripts**

They are now fully replaced.

```bash
git rm -r skills/meeting-digest/scripts
python -m pytest -v
```

Expected: the full suite still passes — nothing imports the scripts.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: add the meeting-digest CLI and remove the standalone scripts"
```

---

### Task 12: `validate`, `mark-inspected`, and `run`

**Files:**
- Modify: `src/meeting_digest/cli.py`
- Modify: `src/meeting_digest/pipeline.py`
- Test: `tests/test_cli_new_commands.py`

**Interfaces:**
- Consumes: `manifest.validate_meeting`, `manifest.mark_inspected`, every pipeline function.
- Produces: `pipeline.run_all(video, output, settings, settings_record, transcribe_options, diarize_options) -> Path`.

- [ ] **Step 1: Write the failing tests**

```python
import json

import pytest

from meeting_digest.cli import build_parser, main
from meeting_digest.manifest import write_json


def make_meeting(tmp_path):
    directory = tmp_path / "meeting"
    (directory / "frames").mkdir(parents=True)
    (directory / "frames" / "frame-00001-0.000s.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    write_json(
        directory / "frames.json",
        {
            "source": "/tmp/a.mp4",
            "duration": 10.0,
            "timestamp_basis": "seconds relative to container start",
            "sampled_frames": 20,
            "settings": {},
            "frames": [
                {
                    "id": "frame-00001",
                    "timestamp": 0.0,
                    "reason": "initial",
                    "approximate_change_start": None,
                    "path": "frames/frame-00001-0.000s.png",
                    "inspected": False,
                }
            ],
        },
    )
    return directory


def test_validate_accepts_a_good_meeting(tmp_path, capsys):
    assert main(["validate", str(make_meeting(tmp_path))]) == 0
    assert "valid" in capsys.readouterr().out.lower()


def test_validate_reports_problems_and_exits_two(tmp_path, capsys):
    directory = make_meeting(tmp_path)
    (directory / "frames" / "frame-00001-0.000s.png").unlink()
    assert main(["validate", str(directory)]) == 2
    assert "frame-00001" in capsys.readouterr().err


def test_mark_inspected_updates_the_manifest(tmp_path, capsys):
    directory = make_meeting(tmp_path)
    assert main(["mark-inspected", str(directory), "frame-00001"]) == 0
    data = json.loads((directory / "frames.json").read_text(encoding="utf-8"))
    assert data["frames"][0]["inspected"] is True


def test_mark_inspected_rejects_an_unknown_id(tmp_path, capsys):
    assert main(["mark-inspected", str(make_meeting(tmp_path)), "frame-42"]) == 2
    assert "frame-42" in capsys.readouterr().err


def test_run_accepts_the_pipeline_flags():
    args = build_parser().parse_args(["run", "a.mp4", "out", "--language", "de"])
    assert args.command == "run"
    assert args.language == "de"
    assert args.model == "small"
```

- [ ] **Step 2: Run them and watch them fail**

Run: `python -m pytest tests/test_cli_new_commands.py -v`
Expected: FAIL — `invalid choice: 'validate'`

- [ ] **Step 3: Add `run_all` to `pipeline.py`**

```python
def run_all(
    video: Path,
    output: Path,
    settings: ScanSettings,
    settings_record: dict,
    transcribe_options: dict,
    diarize_options: dict,
) -> Path:
    """Run the whole ingestion pipeline into a fresh meeting directory."""
    if output.exists() and any(output.iterdir()):
        raise DigestError(f"Output directory is not empty; use a fresh one: {output}")
    audio_path = output / "audio.wav"
    extract_audio(video, audio_path)
    select_frames(video, output, settings, None, None, settings_record)
    raw = write_transcript(audio_path, output, **transcribe_options)
    turns = write_speaker_turns(audio_path, output / "speaker_turns.json", **diarize_options)
    write_labeled_transcript(raw, turns, output)
    return output
```

Add `from meeting_digest.audio import extract_audio` to `pipeline.py`'s imports.

- [ ] **Step 4: Add the three subparsers to `build_parser()`**

Insert before `return parser`:

```python
    validate = sub.add_parser("validate", help="Check a meeting directory against the contract")
    validate.add_argument("directory", type=Path)

    inspected = sub.add_parser(
        "mark-inspected", help="Record that frames have been visually inspected"
    )
    inspected.add_argument("directory", type=Path)
    inspected.add_argument("frame_ids", nargs="+", metavar="FRAME_ID")

    run_cmd = sub.add_parser("run", help="Run the whole pipeline into one directory")
    run_cmd.add_argument("video", type=Path)
    run_cmd.add_argument("output", type=Path)
    run_cmd.add_argument("--sample-fps", type=float, default=2)
    run_cmd.add_argument("--stable-seconds", type=float, default=1)
    run_cmd.add_argument("--motion-interval", type=float, default=5)
    run_cmd.add_argument("--max-gap", type=float, default=30)
    run_cmd.add_argument("--pixel-threshold", type=float, default=20)
    run_cmd.add_argument("--change-ratio", type=float, default=0.015)
    run_cmd.add_argument("--tile-ratio", type=float, default=0.12)
    run_cmd.add_argument("--crop", default=None, help=argparse.SUPPRESS)
    run_cmd.add_argument("--timestamps", default=None, help=argparse.SUPPRESS)
    run_cmd.add_argument("--model", default="small")
    run_cmd.add_argument("--language")
    run_cmd.add_argument("--device", default="cpu")
    run_cmd.add_argument("--compute-type", default="int8")
    run_cmd.add_argument("--diarization-model", default=DEFAULT_MODEL)
    run_cmd.add_argument("--min-speakers", type=_positive_int)
    run_cmd.add_argument("--max-speakers", type=_positive_int)
```

- [ ] **Step 5: Add the three branches to `_run_command()`**

`validate` runs before `require_dependencies()` — checking a finished folder needs no ffmpeg. Put these immediately after the `check` branch:

```python
    if args.command == "validate":
        problems = validate_meeting(args.directory)
        if problems:
            for problem in problems:
                print(f"error: {problem}", file=sys.stderr)
            return 2
        print(f"{args.directory} is valid.")
        return 0

    if args.command == "mark-inspected":
        count = mark_inspected(args.directory, args.frame_ids)
        print(f"Marked {count} frame(s) inspected in {args.directory / 'frames.json'}")
        return 0
```

And after the `label` branch:

```python
    elif args.command == "run":
        settings, record = _scan_settings(parser, args)
        print(pipeline.run_all(
            args.video,
            args.output,
            settings,
            record,
            {
                "model": args.model,
                "language": args.language,
                "device": args.device,
                "compute_type": args.compute_type,
            },
            {
                "model": args.diarization_model,
                "min_speakers": args.min_speakers,
                "max_speakers": args.max_speakers,
            },
        ))
```

Add to `cli.py`'s imports:

```python
from meeting_digest.manifest import mark_inspected, validate_meeting
```

- [ ] **Step 6: Run them and watch them pass**

Run: `python -m pytest tests/test_cli_new_commands.py -v`
Expected: 5 passed.

- [ ] **Step 7: Run everything and lint**

```bash
python -m pytest -v
ruff check . && ruff format --check .
meeting-digest --help
```

Expected: all green; `--help` lists all nine commands.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: add validate, mark-inspected and run commands"
```

**BATCH D CHECKPOINT — stop for review.**

---

# Batch E — End-to-end

### Task 13: Synthetic media E2E test

**Files:**
- Create: `tests/conftest.py`, `tests/test_e2e.py`

**Interfaces:**
- Consumes: the installed `meeting-digest` command and every module.
- Produces: a `synthetic_meeting` pytest fixture returning a `Path` to a generated MP4.

- [ ] **Step 1: Write `tests/conftest.py`**

The clip is built, so the right answer is known before the test runs: colour changes at 1.0 s and 3.0 s mean three distinct screens.

```python
import shutil
import subprocess

import pytest


def _have_ffmpeg() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


requires_ffmpeg = pytest.mark.skipif(not _have_ffmpeg(), reason="ffmpeg and ffprobe required")


@pytest.fixture(scope="session")
def synthetic_meeting(tmp_path_factory):
    """A 5-second clip whose screen changes at exactly 1.0s and 3.0s.

    Three solid colour fields concatenated, plus a sine tone, so the expected
    number of distinct screens is known without any detection heuristic.
    """
    if not _have_ffmpeg():
        pytest.skip("ffmpeg and ffprobe required")
    directory = tmp_path_factory.mktemp("media")
    video = directory / "meeting.mp4"
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y",
            "-f", "lavfi", "-i",
            "color=c=red:s=640x360:d=1[a];"
            "color=c=green:s=640x360:d=2[b];"
            "color=c=blue:s=640x360:d=2[c];"
            "[a][b][c]concat=n=3:v=1:a=0,fps=30[v]",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
            "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
            "-c:a", "aac", "-shortest",
            str(video),
        ],
        check=True,
        capture_output=True,
    )
    return video
```

- [ ] **Step 2: Write the failing E2E test**

```python
import json
import wave

import pytest

from meeting_digest.cli import main
from meeting_digest.manifest import validate_meeting
from tests.conftest import requires_ffmpeg

pytestmark = [requires_ffmpeg, pytest.mark.slow]


def test_extract_audio_produces_mono_16k_pcm(synthetic_meeting, tmp_path):
    output = tmp_path / "out" / "audio.wav"
    assert main(["extract-audio", str(synthetic_meeting), str(output)]) == 0
    with wave.open(str(output), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getframerate() == 16000
        assert wav.getsampwidth() == 2
        assert wav.getnframes() > 16000 * 4


def test_extract_audio_refuses_to_overwrite(synthetic_meeting, tmp_path, capsys):
    output = tmp_path / "out" / "audio.wav"
    main(["extract-audio", str(synthetic_meeting), str(output)])
    assert main(["extract-audio", str(synthetic_meeting), str(output)]) == 2
    assert "already exists" in capsys.readouterr().err


def test_frames_finds_the_three_distinct_screens(synthetic_meeting, tmp_path):
    output = tmp_path / "out"
    assert main(["frames", str(synthetic_meeting), str(output)]) == 0
    data = json.loads((output / "frames.json").read_text(encoding="utf-8"))

    timestamps = [frame["timestamp"] for frame in data["frames"]]
    assert len(timestamps) >= 3, f"expected at least 3 candidates, got {timestamps}"

    # One candidate near each colour field, within the sampling period (0.5s)
    # plus the 1.0s stability window.
    for expected in (0.0, 1.0, 3.0):
        assert any(abs(t - expected) <= 1.5 for t in timestamps), (
            f"no candidate near {expected}s in {timestamps}"
        )


def test_frames_manifest_matches_the_contract(synthetic_meeting, tmp_path):
    output = tmp_path / "out"
    main(["frames", str(synthetic_meeting), str(output)])
    data = json.loads((output / "frames.json").read_text(encoding="utf-8"))
    assert data["duration"] == pytest.approx(5.0, abs=0.2)
    assert data["sampled_frames"] > 0
    for frame in data["frames"]:
        assert frame["id"].startswith("frame-")
        assert (output / frame["path"]).stat().st_size > 0
        assert frame["inspected"] is False
    assert validate_meeting(output) == []


def test_frames_extracts_explicit_timestamps(synthetic_meeting, tmp_path):
    output = tmp_path / "out"
    assert main(["frames", str(synthetic_meeting), str(output), "--timestamps", "0.5,2.0"]) == 0
    data = json.loads((output / "frames.json").read_text(encoding="utf-8"))
    assert [f["reason"] for f in data["frames"]] == ["requested", "requested"]
    assert data["sampled_frames"] == 0


def test_frames_rejects_a_timestamp_past_the_end(synthetic_meeting, tmp_path, capsys):
    output = tmp_path / "out"
    assert main(["frames", str(synthetic_meeting), str(output), "--timestamps", "99"]) == 2
    assert "outside the video timeline" in capsys.readouterr().err


def test_frames_refuses_a_reused_directory(synthetic_meeting, tmp_path, capsys):
    output = tmp_path / "out"
    main(["frames", str(synthetic_meeting), str(output)])
    assert main(["frames", str(synthetic_meeting), str(output)]) == 2
    assert "already exist" in capsys.readouterr().err


def test_frames_honours_a_crop(synthetic_meeting, tmp_path):
    output = tmp_path / "out"
    assert main([
        "frames", str(synthetic_meeting), str(output), "--crop", "0,0,320,180"
    ]) == 0
    data = json.loads((output / "frames.json").read_text(encoding="utf-8"))
    assert data["settings"]["crop"] == "0,0,320,180"
    # Saved PNGs stay full-resolution even though comparison was cropped.
    assert len(data["frames"]) >= 3
```

- [ ] **Step 3: Run and watch it fail or pass**

Run: `python -m pytest tests/test_e2e.py -v`

If `test_frames_finds_the_three_distinct_screens` fails, print the actual timestamps and reasons before changing any threshold — the defaults are the shipped behavior and must not be tuned to make a test pass. If the clip's encoding is smoothing the transitions, adjust the *fixture* (longer fields, `-tune stillimage`), not the detection defaults.

- [ ] **Step 4: Run the whole suite**

```bash
python -m pytest -v
```

Expected: all green. Note the runtime; if E2E exceeds ~30 s, reduce the fixture to session scope reuse rather than trimming assertions.

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py tests/test_e2e.py
git commit -m "test: add end-to-end coverage against ffmpeg-generated media"
```

**BATCH E CHECKPOINT — stop for review.**

---

# Batch F — CI and skills

### Task 14: CI and the plugin manifest

**Files:**
- Create: `.github/workflows/ci.yml`, `.github/workflows/nightly.yml`, `.claude-plugin/marketplace.json`

**Interfaces:**
- Consumes: `pyproject.toml`'s `dev` extra and the `skills/` layout.
- Produces: nothing other code imports.

- [ ] **Step 1: Write `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: pyproject.toml

      - name: Install FFmpeg
        run: sudo apt-get update && sudo apt-get install -y ffmpeg

      - name: Install the package
        run: python -m pip install -e ".[dev]"

      - name: Lint
        run: |
          ruff check .
          ruff format --check .

      - name: Test
        run: python -m pytest -v
```

- [ ] **Step 2: Write `.github/workflows/nightly.yml`**

The install check is the part that protects the "installable on someone else's device" goal.

```yaml
name: Nightly

on:
  schedule:
    - cron: "0 3 * * *"
  workflow_dispatch:

jobs:
  cross-platform:
    strategy:
      fail-fast: false
      matrix:
        os: [windows-latest, macos-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: pyproject.toml

      - name: Install FFmpeg (macOS)
        if: runner.os == 'macOS'
        run: brew install ffmpeg

      - name: Install FFmpeg (Windows)
        if: runner.os == 'Windows'
        run: choco install ffmpeg -y --no-progress

      - name: Install the package
        run: python -m pip install -e ".[dev]"

      - name: Verify the console script is on PATH
        run: |
          meeting-digest --version
          meeting-digest --help
          meeting-digest check

      - name: Test
        run: python -m pytest -v
```

- [ ] **Step 3: Write `.claude-plugin/marketplace.json`**

```json
{
  "name": "meeting-digest",
  "owner": {
    "name": "Davin Dewanto",
    "url": "https://github.com/davin-advasol"
  },
  "plugins": [
    {
      "name": "meeting-digest",
      "source": "./",
      "description": "Digest recorded meetings into speaker-labeled transcripts, presentation screenshots, and evidence-linked notes, then answer questions about them.",
      "version": "0.1.0",
      "author": { "name": "Davin Dewanto" },
      "homepage": "https://github.com/davin-advasol/meeting-digest",
      "license": "MIT",
      "keywords": ["meetings", "transcription", "diarization", "notes"]
    }
  ]
}
```

- [ ] **Step 4: Validate the JSON and the workflows locally**

```bash
python -c "import json,pathlib; json.loads(pathlib.Path('.claude-plugin/marketplace.json').read_text()); print('marketplace.json ok')"
python -c "import sys; sys.exit(0)"
```

For the workflows, confirm they parse:

```bash
python -c "
import pathlib
for p in pathlib.Path('.github/workflows').glob('*.yml'):
    text = p.read_text()
    assert 'runs-on' in text, p
    print(p, 'ok')
"
```

- [ ] **Step 5: Commit and push so CI actually runs**

```bash
git add .github .claude-plugin
git commit -m "ci: add test workflow, nightly cross-platform install check, and plugin manifest"
git push
```

Then report the Actions run result to the user. A red first run is normal — read the log and fix the cause rather than disabling the step.

---

### Task 15: Update both skills for the CLI

**Files:**
- Modify: `skills/meeting-digest/SKILL.md`
- Modify: `skills/meeting-digest/references/setup.md`
- Create: `skills/meeting-digest/references/artifacts.md`
- Modify: `skills/meeting-assistant/SKILL.md`

**Interfaces:**
- Consumes: the CLI surface from Tasks 11–12.
- Produces: the contract document `skills/meeting-digest/references/artifacts.md`, which `skills/meeting-assistant/SKILL.md` and `docs/artifacts.md` both point at.

- [ ] **Step 1: Replace every script invocation in `skills/meeting-digest/SKILL.md`**

| Find | Replace with |
|---|---|
| `python <skill>/scripts/select_frames.py --check` | `meeting-digest check` |
| `python <skill>/scripts/extract_audio.py <video> <output>/audio.wav` | `meeting-digest extract-audio <video> <output>/audio.wav` |
| `python <skill>/scripts/select_frames.py <video> <output>` | `meeting-digest frames <video> <output>` |
| `select_frames.py <video> <fresh-output> --timestamps 120.5,123,126` | `meeting-digest frames <video> <fresh-output> --timestamps 120.5,123,126` |
| `select_frames.py --help` | `meeting-digest frames --help` |
| `transcribe_local.py` | `meeting-digest transcribe` |
| `diarize_local.py` | `meeting-digest diarize` |
| `label_speakers.py` | `meeting-digest label` |

- [ ] **Step 2: Replace the two contract sections in `skills/meeting-digest/SKILL.md`**

Delete the `## Transcript contract` and `## Frame-selection interpretation` sections and put this in their place:

```markdown
## Artifact formats

Every file this skill writes — and everything `meeting-assistant` later reads — is
specified in [the artifact contract](references/artifacts.md). Run
`meeting-digest validate <output>/` to check a meeting directory against it before
relying on the results.

The frame scan is approximate, not guaranteed slide detection. Short-lived content,
small text edits, animations, and changing webcam layouts can escape detection or
create extra candidates. Increase `--sample-fps` for fast demos and use
`--timestamps` for anything ambiguous. See `meeting-digest frames --help` for
thresholds and crop options.
```

- [ ] **Step 3: Add a step 4 note about `mark-inspected` in `skills/meeting-digest/SKILL.md`**

In the workflow's point 4, after the sentence about caching visual findings, add:

```markdown
Record inspected frames with `meeting-digest mark-inspected <output>/ frame-00003 frame-00007`
rather than editing `frames.json` by hand.
```

- [ ] **Step 4: Rewrite the install section of `skills/meeting-digest/references/setup.md`**

Replace the `## Local environment` code block and the `requirements.txt` sentence:

```markdown
## Local environment

Required: Python 3.10+, FFmpeg and ffprobe on PATH, and the `meeting-digest`
package. FFmpeg is a separate executable, not supplied by the Python package named
`ffmpeg`. Install it from a trusted platform package or an
[FFmpeg-listed build](https://ffmpeg.org/download.html). Then:

```
python -m pip install git+https://github.com/davin-advasol/meeting-digest.git
meeting-digest check
```

`meeting-digest check` reports whether FFmpeg, ffprobe, NumPy, and OpenCV are all
available. The install pulls PyTorch, so expect a multi-gigabyte download on a
clean machine; a GPU setup may require a platform-specific PyTorch build. Local
comparison consumes CPU and disk, not model tokens. Keep original recordings
outside version control unless the project explicitly tracks them.
```

Then replace the three-command block further down:

```
meeting-digest transcribe <meeting>/audio.wav <meeting> --model small
meeting-digest diarize <meeting>/audio.wav <meeting>/speaker_turns.json
meeting-digest label <meeting>/transcript_raw.json <meeting>/speaker_turns.json <meeting>
```

And change the `--min-speakers`/`--max-speakers` sentence to reference
`meeting-digest diarize --min-speakers N --max-speakers N`.

- [ ] **Step 5: Write `skills/meeting-digest/references/artifacts.md`**

This is the single source both skills point at. It lives inside the skill so a
standalone skill install still has it.

```markdown
# Artifact contract

Every file a digested meeting contains, who writes it, and what it guarantees.
`meeting-digest validate <meeting>/` checks a directory against this document.

A meeting directory is `<project>/meetings/<date>-<recording-stem>/`.

## Files

| File | Written by | Required keys |
|---|---|---|
| `audio.wav` | `meeting-digest extract-audio` | Mono, 16 kHz, signed 16-bit PCM, offset-corrected to the video timeline |
| `transcript_raw.json` | `meeting-digest transcribe` | `source`, `language`, `backend`, `segments[]` |
| `transcript_raw.md` | `meeting-digest transcribe` | Readable rendering of the above |
| `speaker_turns.json` | `meeting-digest diarize` | `source`, `backend`, `min_speakers`, `max_speakers`, `turns[]`, `has_overlaps` |
| `transcript.json` | `meeting-digest label` | `source`, `language`, `backend`, `speakers`, `segments[]`, `note` |
| `transcript.md` | `meeting-digest label` | Readable rendering; `Speaker uncertain` where `speaker` is null |
| `frames.json` | `meeting-digest frames` | `source`, `duration`, `timestamp_basis`, `sampled_frames`, `settings`, `frames[]` |
| `frames/*.png` | `meeting-digest frames` | Full-resolution screenshots named `frame-NNNNN-<seconds>s.png` |
| `visual-notes.md` | the agent | Cached visual findings: frame id, image path, timestamp, findings, limits |
| `notes.md` | the agent | From the meeting-notes template |
| `decisions.md` | the agent | Decisions, actions, open questions |
| `meetings/index.md` | the agent (`meeting-assistant`) | Cross-meeting navigation aid, one level up |

## Segment and turn shape

`transcript.json.segments[]`:

- `start`, `end` — seconds relative to the original video, numeric, finite,
  non-negative, `end >= start`
- `text` — string
- `speaker` — `Speaker N` or `null`. Null means no reliable match or overlapping
  speech, never a guess.

`speaker_turns.json.turns[]`:

- `start`, `end` — same rules
- `source_speaker` — the diarization backend's own label, e.g. `SPEAKER_00`

Overlapping turns are preserved even when the readable transcript cannot attribute
the overlapping words. `transcript.json` and `speaker_turns.json` must name the
same `source` audio file.

## Frame shape

`frames.json.frames[]`:

- `id` — `frame-NNNNN`, unique within the file
- `timestamp` — seconds, numeric, finite, non-negative
- `reason` — one of `initial`, `settled_change`, `motion_fallback`, `coverage`,
  `final_change`, `requested`
- `approximate_change_start` — seconds or `null`
- `path` — relative to the meeting directory; must resolve to a non-empty file
- `inspected` — boolean. Set it with `meeting-digest mark-inspected`, never by
  hand. It records that a frame was previously reviewed, not that its content is
  in the current model context.

## Encoding

All JSON and Markdown is UTF-8. Transcript JSON is written with
`ensure_ascii=False` so non-ASCII speech survives round-tripping.

## Timestamps

All times are seconds relative to the container start, accounting for
audio/video stream start offsets. `transcript.md` and `transcript_raw.md` render
them as `HH:MM:SS.mmm`.
```

- [ ] **Step 6: Update `skills/meeting-assistant/SKILL.md`**

Two edits only:

1. In the "Retrieve progressively" section, after the table, add:

```markdown
The exact shape of each artifact is specified in the meeting-digest skill's
[artifact contract](../meeting-digest/references/artifacts.md).
```

2. Replace "set the matching manifest entry's `inspected` field to true when present" with:

```markdown
set the matching manifest entry's `inspected` field with
`meeting-digest mark-inspected <meeting>/ <frame-id>` when the command is available
```

- [ ] **Step 7: Create `docs/artifacts.md` as a pointer**

```markdown
# Artifact contract

The contract lives inside the skill so it survives a standalone skill install:
[`skills/meeting-digest/references/artifacts.md`](../skills/meeting-digest/references/artifacts.md).
```

- [ ] **Step 8: Verify no stale references remain**

```bash
grep -rn "scripts/" skills/ || echo "no script paths remain"
grep -rn "requirements.txt" skills/ || echo "no requirements.txt references remain"
grep -rn "transcribe_local\|diarize_local\|label_speakers\|select_frames\|extract_audio" skills/ \
  || echo "no old script names remain"
```

Expected: all three print their "no ... remain" message.

- [ ] **Step 9: Commit**

```bash
git add skills/ docs/artifacts.md
git commit -m "docs: point both skills at the meeting-digest CLI and artifact contract"
```

**BATCH F CHECKPOINT — stop for review.**

The user must now re-run one real meeting through the new CLI. The automated
tests cover the Python; they cannot confirm the agent follows the rewritten
SKILL.md correctly. Report this to them explicitly rather than claiming the
skills are verified.

---

# Batch G — Documentation

### Task 16: README, architecture, ADRs, contributing, changelog

These four documents are independent of each other. If executing with subagents,
this is the one task worth parallelising.

**Files:**
- Modify: `README.md`
- Create: `docs/architecture.md`, `CONTRIBUTING.md`, `CHANGELOG.md`
- Create: `docs/adr/0001-package-plus-cli.md`, `docs/adr/0002-all-dependencies-required.md`, `docs/adr/0003-github-only-distribution.md`, `docs/adr/0004-artifact-contract-inside-the-skill.md`

**Interfaces:**
- Consumes: the finished CLI and skills.
- Produces: nothing other code imports.

- [ ] **Step 1: Write `README.md`**

Sections, in order, with real content — no placeholders:

1. **Title and one-paragraph description.** What it does, stated concretely: local processing, no meeting bot, no cloud upload of the recording.
2. **What you get** — a fenced tree of a real meeting directory, matching the artifact contract exactly.
3. **Install** — the two steps (pip install, then the skill or plugin), plus the FFmpeg and Hugging Face prerequisites stated plainly as separate requirements the install does not provide.
4. **Use** — `meeting-digest run recording.mp4 meetings/2026-09-24-standup/` first, then the individual commands for finer control.
5. **How frame selection works** — sampling at 2 fps, tile-level comparison catching localized slide edits, the five selection reasons, and the fact that no vision model participates in selection.
6. **The two skills** — what each does and how they relate: digest produces, assistant consumes.
7. **Limits** — approximate slide detection, ASR errors on names and technical terms, speaker numbers being local to each recording, and the fact that a proposal on a slide is not an approved decision. This section is not optional; it is what makes the tool trustworthy.
8. **Development** — link to `CONTRIBUTING.md`.
9. **License** — MIT.

Every command in the README must be one that exists. Verify each by running it.

- [ ] **Step 2: Write `docs/architecture.md`**

Cover: the module boundaries and why `ffmpeg.py` is the only subprocess caller;
the data flow from video through audio, frames, transcript, and turns to labeled
transcript; where the agent's own work (notes, visual inspection) sits relative to
the deterministic pipeline; and why the artifact contract exists as a shared
interface between the two skills.

- [ ] **Step 3: Write the four ADRs**

Each one uses this structure, with the rationale from the spec's decision table:

```markdown
# N. <Title>

Date: 2026-09-24
Status: Accepted

## Context

<The situation that forced a choice.>

## Decision

<What was chosen.>

## Consequences

<What this makes easy, what it makes hard, and what was given up.>
```

ADR 0002 must state the accepted cost plainly: a ~4 GB install even for
screenshot-only use, and a CI matrix reduced to one Linux job because of it.

- [ ] **Step 4: Write `CONTRIBUTING.md`**

Dev setup (`pip install -e ".[dev]"`), running tests (`python -m pytest`), running
lint (`ruff check . && ruff format .`), the ffmpeg requirement for the E2E tests,
the Conventional Commits convention, and a note that changes to the artifact
contract require updating `skills/meeting-digest/references/artifacts.md` and
`manifest.validate_meeting` together.

- [ ] **Step 5: Write `CHANGELOG.md`**

```markdown
# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-24

### Added

- `meeting-digest` command with `check`, `extract-audio`, `frames`, `transcribe`,
  `diarize`, `label`, `validate`, `mark-inspected`, and `run` subcommands.
- The `meeting-digest` Agent Skill for ingesting recordings.
- The `meeting-assistant` Agent Skill for answering questions about ingested meetings.
- A written artifact contract with runtime validation.

### Fixed

- Frame selection no longer fails with a `KeyError` on containers that omit
  `format.duration`; it falls back to the stream duration.
```

- [ ] **Step 6: Verify every documented command actually runs**

```bash
meeting-digest --help
for cmd in check extract-audio frames transcribe diarize label validate mark-inspected run; do
  meeting-digest "$cmd" --help > /dev/null && echo "$cmd ok"
done
```

Expected: nine `ok` lines.

- [ ] **Step 7: Final full check**

```bash
python -m pytest -v
ruff check . && ruff format --check .
git status --short
```

Expected: all tests pass, no lint errors, no unintended untracked files.

- [ ] **Step 8: Commit and push**

```bash
git add -A
git commit -m "docs: add README, architecture, ADRs, contributing guide and changelog"
git push
```

**BATCH G CHECKPOINT — stop for review.**

---

## Done when

- `pip install git+https://github.com/davin-advasol/meeting-digest.git` on a clean
  machine yields a working `meeting-digest` command.
- `python -m pytest` is green; CI is green on `main`.
- Both skills reference only CLI commands — no script paths, no `<skill>/` placeholders.
- `meeting-digest validate` accepts a directory produced by `meeting-digest run`.
- The user has re-run one real meeting through the new CLI and confirmed the
  skills still behave correctly.
