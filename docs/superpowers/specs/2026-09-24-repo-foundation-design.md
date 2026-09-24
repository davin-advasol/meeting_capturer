# Repo foundation: meeting-digest as an installable skill package

Date: 2026-09-24
Status: approved, not yet implemented

## Context

The repository currently tracks an abandoned FastAPI backend (`backend/`) plus its
design docs. That code has been moved aside into an untracked `old/` directory, so
every tracked path shows as deleted in the working tree.

The work that matters now lives in two untracked directories, both written and
manually verified:

- `meeting-digest/` — an Agent Skill that turns a recorded meeting video into a
  speaker-labeled transcript, selected presentation screenshots, and
  evidence-linked notes. Five Python scripts, ~480 lines, all local processing.
- `meeting-assistant/` — a prose-only Agent Skill that answers questions and
  prepares briefings from meetings already ingested by `meeting-digest`.

Neither is in git. There is no packaging, no CI, no root README, and no license
covering them.

## Goals

1. Make the repository explicitly about these two skills.
2. Make the tooling installable on someone else's machine with a documented,
   repeatable command.
3. Make the code legible and verifiable to a reader evaluating it — tests that
   run, CI that proves they pass, docs that explain the design.
4. Turn the artifact formats the two skills share into a written, validated
   contract.

## Non-goals

- Publishing to PyPI. Deferred; GitHub install only.
- Any new user-facing capability. The Q&A capability already exists as
  `meeting-assistant`; this spec only packages and documents it.
- Reworking either SKILL.md's guidance. Prose changes are limited to path
  updates, the new CLI command names, and links to the artifact contract.

## Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | Audience is public **and** portfolio | Drives full docs, license, CI, release hygiene |
| 2 | Python package + CLI; skills wrap the CLI | Makes the logic importable and therefore testable; usable without an agent |
| 3 | All dependencies required, one install | User's call: the skill is only useful with the whole pipeline present |
| 4 | Keep git history; rename repo to `meeting-digest` | History shows an honest pivot; package name matches repo name |
| 5 | GitHub-only distribution | No release machinery before there are users; PyPI stays available later |
| 6 | Unit tests + synthetic-media E2E | Proves the real logic and the real ffmpeg invocations, without committing binaries |
| 7 | Repo keeps the name `meeting-digest` | Ingestion is the core; the assistant ships as a companion skill |

### On decision 3

All dependencies required means `pip install` pulls Torch (~4 GB) even for someone
who only wants screenshots. The accepted consequence is that CI installs Torch on
every run, so the matrix collapses to a single Linux job with an aggressive pip
cache. Windows and macOS coverage moves to a scheduled nightly run.

### On decision 7

`meeting-assistant` is not a "subskill". Claude Code skills are flat — there is no
nesting mechanism and no way to declare a dependency between them. The relationship
is expressed by two things only: each skill's `description` frontmatter names the
other, and the assistant reads the artifacts the digest writes. That makes the
artifact formats a shared interface, which is why they get their own spec document
and runtime validation.

## Repo identity and migration

- GitHub repo renamed `meeting_capturer` → `meeting-digest` (manual, in Settings).
- Local directory renamed to match; `git remote set-url` updated.
- Git history preserved. One commit removes `backend/`, the old
  `docs/superpowers/plans/` and `docs/superpowers/specs/` entries for the
  abandoned v1, and adds the new tree.
- `old/` deleted — it duplicates content already recoverable from history.

## Layout

```
meeting-digest/
├─ pyproject.toml              packaging, dependencies, ruff + pytest config
├─ README.md
├─ LICENSE
├─ CHANGELOG.md
├─ CONTRIBUTING.md
├─ .gitignore
├─ src/meeting_digest/
│   ├─ __init__.py             __version__
│   ├─ cli.py                  argparse, subcommand dispatch, input validation
│   ├─ errors.py               DigestError → clean message, exit code 2
│   ├─ ffmpeg.py               probe / run / stream_gray_frames — the only module that shells out
│   ├─ timeline.py             audio-video offset math, stamp()
│   ├─ audio.py                extract_audio()
│   ├─ frames.py               Thresholds, changed(), Selector, scan()
│   ├─ transcribe.py           faster-whisper wrapper
│   ├─ diarize.py              pyannote wrapper, load_pcm16_mono()
│   ├─ labeling.py             speaker_for(), label()
│   └─ manifest.py             artifact schemas: write and validate
├─ skills/
│   ├─ meeting-digest/
│   │   ├─ SKILL.md
│   │   ├─ references/setup.md
│   │   └─ assets/meeting-notes.md
│   └─ meeting-assistant/
│       └─ SKILL.md
├─ .claude-plugin/
│   └─ marketplace.json        one plugin, installs both skills
├─ tests/
├─ docs/
│   ├─ architecture.md
│   ├─ artifacts.md            the shared artifact contract
│   ├─ adr/
│   └─ superpowers/specs/
└─ .github/workflows/
    ├─ ci.yml
    └─ nightly.yml
```

`agents/openai.yaml` from each existing skill directory is preserved in place
under `skills/<name>/agents/openai.yaml`.

## CLI surface

```
meeting-digest check
meeting-digest extract-audio VIDEO OUT/audio.wav
meeting-digest frames VIDEO OUT [--crop X,Y,W,H] [--timestamps T1,T2,...]
                                [--sample-fps] [--stable-seconds] [--motion-interval]
                                [--max-gap] [--pixel-threshold] [--change-ratio] [--tile-ratio]
meeting-digest transcribe OUT/audio.wav OUT [--model small] [--language de]
                                            [--device cpu] [--compute-type int8]
meeting-digest diarize OUT/audio.wav OUT/speaker_turns.json
                                     [--model] [--min-speakers N] [--max-speakers N]
meeting-digest label OUT/transcript_raw.json OUT/speaker_turns.json OUT
meeting-digest validate OUT/
meeting-digest mark-inspected OUT/ frame-00003 [frame-00007 ...]
meeting-digest run VIDEO OUT
```

Flags and defaults carry over unchanged from the current scripts. Three commands
are new:

- **`run`** — chains extract-audio → frames → transcribe → diarize → label so the
  README can show one command that produces a full meeting folder.
- **`validate`** — checks a meeting directory against the artifact contract.
- **`mark-inspected`** — flips `inspected` to `true` for named frame ids in
  `frames.json`. Exists because `meeting-assistant`'s instructions tell the agent
  to update that field; an atomic validated write is safer than hand-editing JSON.

Every command preserves the existing refuse-to-overwrite behavior: an existing
output path is an error, not a silent overwrite.

## Artifact contract (`docs/artifacts.md`)

Both skills link to this document instead of restating formats. It specifies, for
a meeting directory:

| File | Written by | Contents |
|---|---|---|
| `audio.wav` | `extract-audio` | Mono 16 kHz signed 16-bit PCM, offset-corrected to the video timeline |
| `transcript_raw.json` | `transcribe` | `source`, `language`, `backend`, `segments[]` with word-level timings |
| `transcript_raw.md` | `transcribe` | Readable form of the above |
| `speaker_turns.json` | `diarize` | `source`, `backend`, `min_speakers`, `max_speakers`, `turns[]`, `has_overlaps` |
| `transcript.json` | `label` | `source`, `language`, `backend`, `speakers`, `segments[]` with `speaker` (or null) |
| `transcript.md` | `label` | Readable form, `Speaker uncertain` for null |
| `frames.json` | `frames` | `source`, `duration`, `timestamp_basis`, `sampled_frames`, `settings`, `frames[]` |
| `frames/*.png` | `frames` | Full-resolution screenshots, `frame-NNNNN-<seconds>s.png` |
| `visual-notes.md` | agent | Cached visual findings: frame id, path, timestamp, findings, limits |
| `notes.md` | agent | From `skills/meeting-digest/assets/meeting-notes.md` |
| `decisions.md` | agent | Decisions, actions, open questions |
| `meetings/index.md` | agent (`meeting-assistant`) | Cross-meeting navigation aid |

Invariants `validate` enforces: numeric, finite, non-negative, ordered time
intervals; frame `path` values resolve to existing non-empty files; `frames[]` ids
are unique and match their filenames; `transcript.json` and `speaker_turns.json`
agree on `source`; required keys present.

## Refactor

Behavior-preserving. Logic moves out of each script's `main()` into functions that
take plain values rather than an argparse namespace — `changed(a, b, args)` becomes
`changed(a, b, thresholds)` where `thresholds` is a frozen dataclass. Argument
parsing and validation consolidate in `cli.py`; the modules raise `DigestError`.

The `global cv2, np` deferred-import trick in `select_frames.py` is removed, since
dependencies are now hard requirements.

Mapping:

| Current | Becomes |
|---|---|
| `extract_audio.py` probe + filter construction | `timeline.py` (offset math), `audio.py` (extraction), `ffmpeg.py` (subprocess) |
| `select_frames.py` `changed`, `Selector` | `frames.py` |
| `select_frames.py` `probe`, `scan` subprocess plumbing | `ffmpeg.py` |
| `select_frames.py` manifest assembly | `manifest.py` |
| `transcribe_local.py` | `transcribe.py` + `timeline.stamp` |
| `diarize_local.py` | `diarize.py` |
| `label_speakers.py` `speaker_for`, `label` | `labeling.py` |

### One bug fixed test-first

`select_frames.py:probe()` reads `data['format']['duration']` unguarded. Containers
that omit it — some MKV files, fragmented MP4 — raise `KeyError`. The replacement
falls back to the video stream's `duration`, then to a `DigestError` naming the
file and the missing field.

## Testing

**Unit** — pure logic, in memory, no subprocess:

- `timeline.py`: audio starting before / after / level with video; missing
  `start_time`; missing container duration falling back to stream duration
- `frames.py`: `changed()` with a small high-contrast region (tile ratio trips,
  overall ratio does not) and with diffuse low-level noise (neither trips);
  `Selector` producing each reason — `initial`, `settled_change`,
  `motion_fallback`, `coverage`, `final_change`
- `labeling.py`: `speaker_for()` for a clean single-turn overlap, a near-tie
  returning `None`, sub-50% overlap returning `None`, and no overlap returning
  `None`; `label()` merging consecutive same-speaker words within 1.5 s
- `manifest.py`: each schema round-trips; `validate` rejects missing keys,
  negative and reversed intervals, duplicate frame ids, and dangling PNG paths
- `cli.py`: argument validation, exit codes, refuse-to-overwrite

**End-to-end with synthetic media** — a pytest fixture builds a 5-second MP4 with
ffmpeg: solid color fields switching at 1 s and 3 s, plus a sine tone. Because the
clip is constructed, the expected result is known in advance. The real CLI then
runs against it and asserts frame count, timestamps within tolerance, `frames.json`
shape, and that `audio.wav` is mono 16 kHz PCM. No binary media is committed.

`faster-whisper` and `pyannote.audio` are faked at their seams. The suite tests
that this code handles their output correctly, not that those models are accurate.

**Contract** — everything `validate` accepts is something a writer produces, and
every malformed shape listed above is rejected.

## CI

`ci.yml`, on push and pull request: ubuntu-latest, Python 3.12, ffmpeg from apt,
pip cache keyed on `pyproject.toml`. Steps: `ruff check` → `ruff format --check` →
`pytest`. Warm runs land around 3–5 minutes; cold runs pay the Torch download.

`nightly.yml`, scheduled and manually dispatchable: the same steps on
windows-latest and macos-latest, plus a bare install-and-invoke check
(`pip install .` then `meeting-digest check` and `--help`) that proves the package
installs on a clean machine of each OS.

## Docs

- **README.md** — what it does, a real sample of the output it produces, install,
  the command set, a short explanation of how frame selection works and why no
  vision model is involved in it, and an explicit limits section covering
  approximate slide detection, ASR error, and speaker-label caveats.
- **docs/architecture.md** — module boundaries, data flow from video to notes,
  and where the two skills sit relative to the package.
- **docs/artifacts.md** — the contract above.
- **docs/adr/** — one short record per decision in the table above.
- **CONTRIBUTING.md** — dev setup, running tests, ruff, how to propose changes.
- **CHANGELOG.md** — Keep a Changelog format, starting at `0.1.0`.

## Installation

```
pip install git+https://github.com/davin-advasol/meeting-digest.git
```

Skills, either by cloning the repo and copying `skills/*` into `~/.claude/skills/`,
or via the plugin marketplace entry:

```
/plugin marketplace add davin-advasol/meeting-digest
```

FFmpeg and ffprobe remain separate prerequisites on PATH, and the pyannote model
still requires accepting its Hugging Face terms and authenticating locally with
`hf auth login`. The README states both plainly; skill installation does not
provide them.

## Milestones

1. **Repo pivot** — rename, delete `old/`, remove `backend/` and stale docs, add
   LICENSE and `.gitignore`
2. **Package skeleton** — `pyproject.toml`, `src/` layout, `cli.py`, ruff config,
   `pip install -e .` works
3. **Artifact contract** — `docs/artifacts.md`, `manifest.py`, `validate`,
   contract tests
4. **Port modules** — one at a time, test-first, behavior preserved
5. **E2E fixture** — synthetic media generation and the end-to-end test
6. **`mark-inspected`** — command plus the `meeting-assistant` SKILL.md updates
   that reference it
7. **CI** — `ci.yml`, `nightly.yml`, plugin manifest
8. **Docs** — README, architecture, ADRs, CONTRIBUTING, CHANGELOG

## Deferred

- PyPI publication and a tag-driven release workflow
- Optional dependency extras, should the 4 GB install prove to be a barrier
- Any new capability in either skill
