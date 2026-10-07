---
name: meeting-digest
description: Digest recorded project meetings in MP4 or other video formats into speaker-labeled transcripts, selected presentation screenshots, and evidence-linked notes, decisions, and requirements. Use for saved meeting recordings and follow-up questions about their spoken or presented content.
---

# Meeting digest

Combine speech and presented content while keeping visual-model usage selective. Keep the source recording intact. Scripts live relative to this skill, but outputs belong to the user's project, never in the installed skill directory.

## Start

Determine the recording and project directory from the request. Default output: `<project>/meetings/<date>-<recording-stem>/`; do not invent a meeting date from the file modification time (use an undated stem if unknown). Use a new directory for a new run, or explicitly reuse existing artifacts without silently overwriting them.

Run `python <skill>/scripts/select_frames.py --check` to check FFmpeg, ffprobe, NumPy, and OpenCV. Read [setup and transcription](references/setup.md) for the separate transcription and speaker-labeling dependencies. Do not claim that skill installation installs these tools, model weights, or credentials.

## Workflow

1. Extract audio using `python <skill>/scripts/extract_audio.py <video> <output>/audio.wav`. Because these meetings have multiple speakers, diarize by default. The local path is `transcribe_local.py` for word-timed `transcript_raw.json`, `diarize_local.py` for `speaker_turns.json`, then `label_speakers.py` for `transcript.json` and `transcript.md`. See [setup and transcription](references/setup.md) for commands. Preserve raw output and reuse existing artifacts when appropriate. Label recurring voices `Speaker 1`, `Speaker 2`, etc. by first detected occurrence; do not infer real names. Mark unclear or overlapping words `Speaker uncertain` and review important attributions against audio. If diarization cannot run, provide the unlabeled transcript with that limitation rather than guessing speaker labels.
2. Run `python <skill>/scripts/select_frames.py <video> <output>`. This streams small samples through local comparisons, saves selected full-resolution PNGs, and writes `frames.json`. No VLM is used. Inspect a few representative images to determine whether a presentation crop is needed; rerun into a fresh directory with `--crop x,y,width,height` in original pixels if appropriate. Do not automatically mask areas that may contain useful presented content. For changing layouts use separate runs or leave the full screen visible.
3. Read the transcript and map relevant segments to the screenshot timeline. Start with frames around explicit visual references and topics needed for the requested documents. Use available image-viewing/model capabilities to actually inspect them. Extract additional evidence with `select_frames.py <video> <fresh-output> --timestamps 120.5,123,126`; inspect before/after the spoken reference. Selection is recoverable from the source MP4.
4. Default to **on-demand visuals**, as agreed: selected screenshots are candidates, not all sent to a VLM. If the user requests comprehensive slide coverage, inspect all distinct candidates, revisit long gaps/continuous motion, and describe remaining sampling limits. Do not silently claim coverage of unseen slides. Cache visual findings with frame IDs, image paths, timestamps, and inspected/uninspected status in `visual-notes.md` to avoid repeated analysis.
5. Produce `notes.md` and `decisions.md` using [the output template](assets/meeting-notes.md). Produce separate requirements/project updates only when requested or clearly within scope. Distinguish what was displayed, what was said, what was agreed, and inference. A proposed feature on a slide is not an approved requirement. Owners and dates must be supported by evidence. Cite transcript times and relative screenshot links for substantive conclusions.
6. Verify evidence links, timestamp alignment, and that important conclusions are supported by inspected material. Report output paths and coverage limitations. When combining meetings, retain each source and date; record changed decisions and conflicts rather than silently overwriting them. Do not modify existing project specifications merely because a meeting contains a proposal.

## Transcript contract

`transcript.json`: an object with `source`, `language` (or null), `backend`, and `segments`. Each segment has numeric `start` and `end` in seconds relative to the original video, `text`, and `speaker` (`Speaker N` or null when uncertain). Check nonnegative, ordered intervals and account for audio/video stream start offsets. Preserve `speaker_turns.json`, including any overlapping turns, even when the readable transcript cannot attribute overlapping words. `transcript.md` presents the same segments with readable timestamps. Write UTF-8.

## Frame-selection interpretation

Defaults are starting heuristics, not guaranteed slide detection: 2 samples/second, 1 second stability, motion fallback every 5 seconds, and a local coverage candidate at least every 30 seconds. Periodic candidates do not automatically incur VLM tokens. Compare with both the preceding sample (motion) and last selected frame (accumulated change), including tile-level differences to catch small slide additions. Continuous motion can generate many candidates; report the count and narrow the VLM selection rather than silently discarding evidence. Revisited slides retain their temporal occurrences.

The scan is approximate: short-lived content, small text edits, animations, and changing webcam layouts can escape detection or create extra candidates. Increase `--sample-fps` for fast demos and use targeted extraction for ambiguities. See `select_frames.py --help` for thresholds and crop options. Full-frame screenshots are retained even when a crop guides comparison.
