---
name: fetch-transcript
description: Turn a recording link or a local audio/video file into a local, speaker-labeled transcript. Saves the audio, then runs the meeting-digest transcription pipeline. Use when the user gives a link to a recorded meeting, call, webinar, video or podcast (a hosting page, a direct media URL, a stream) or a media file and wants its transcript.
---

# Fetch transcript

Get the audio from wherever the recording lives, keep a local copy, and transcribe it locally. `scripts/fetch_transcript.py` (in this skill's directory) does the deterministic work: rungs 1–3 of the source ladder, system-audio recording, and the `meeting-digest` pipeline. You do the judgment and the browser work.

## Before running

- Run from the project root with the Python that imports `meeting_digest`. On Windows that is usually `py`; `python` can be a Microsoft Store alias. Check with `py -c "import meeting_digest"`.
- Needs FFmpeg/ffprobe on PATH, plus `py -m pip install yt-dlp soundcard`. Transcription and speaker-label dependencies, including the Hugging Face model terms, are in [meeting-digest setup](../meeting-digest/references/setup.md).

## Output folder

`<project>/meetings/<YYYY-MM-DD>-<title-slug>/`. Take the title and the meeting date from the source: the page's title and the date it shows, or the file name. Use today's date when the meeting date is unknown. The slug is lowercase ASCII with hyphens. An existing folder for the same meeting may be reused: the script only adds its own files and never touches others.

## Run

```
py <skill-dir>/scripts/fetch_transcript.py meetings/<date>-<slug> [SOURCE] [--language de] [--model small] [--no-speakers]
```

- SOURCE is a local file, a direct media URL, or a page URL. Omit it to read the clipboard.
- Speaker labels are on by default. Auto-detection hears only the first 30 seconds, and meetings often open with small talk in another language. Pass `--language` whenever the title, page or user makes the language evident. Otherwise check `language` in `transcript_raw.json` against a few lines from the middle of `transcript_raw.md`.
- A one-hour recording takes tens of minutes on CPU. Run it in the background and wait for the completion notification. Don't poll.
- Exit codes: `0` done (the last line names the transcript), `1` a step failed, `2` bad input or empty clipboard, `3` rungs 1–3 found no audio, so take the browser rung.

## Source ladder

Cheapest rung first; stop at the first one that yields audio.

| Rung | Who | Test | Action |
|---|---|---|---|
| 1 Local file | script | path exists | use it as is |
| 2 Direct | script | ffprobe finds an audio stream at the URL | stream-copy the audio to `audio.mka` |
| 3 yt-dlp | script | yt-dlp supports the page | best audio only, remuxed to `audio.mka`, no browser cookies |
| 4 Browser | you | exit code 3, or media loads only once played | steps a–f below |

## Browser rung (Claude in Chrome)

a. Open the page. Inspect the media without reading its URL:
   ```js
   const m = document.querySelector('video, audio'); const s = m?.currentSrc || '';
   m && { scheme: s.split(':')[0], host: s.startsWith('http') ? new URL(s).host : null,
          query: s.includes('?'), duration: m.duration, drm: !!m.mediaKeys }
   ```
   If there is no element or `scheme` is empty, press the player's play button so the media loads, then inspect again.
b. `http(s)` with `query: false`: read `m.currentSrc` and rerun the script with it as SOURCE.
c. `query: true`, or the extension blocks the URL: run `fetch_transcript.py --peek`. It prints only whether the clipboard holds an http(s) URL, plus its host and length; the user may have filled it already. If the host matches the media host from step a, or that host was blocked too and the length matches `currentSrc.length`, rerun with no SOURCE; rung 2's ffprobe confirms the audio. Otherwise pause and ask the user to fill the clipboard. The easiest way is to right-click the video and choose "Copy video address", which works when the player shows the browser's native controls. If that isn't available, they can run this in that tab's DevTools Console:
   `copy(document.querySelector('video, audio').currentSrc)`
   If the peek then reports the command's own length (55), the line never ran. Either Chrome's paste guard blocked it (type `allow pasting` first), or the Console's context dropdown isn't on `top`.
d. `blob:` (MediaSource): look for a manifest via `performance.getEntriesByType('resource')`. Return only the hosts of names matching `/\.(m3u8|mpd)(\?|$)/i`. If a manifest URL is readable, rerun with it. If it's blocked, use the clipboard handoff from step c with:
   `copy(performance.getEntriesByType('resource').map(e => e.name).find(n => /\.(m3u8|mpd)(\?|$)/i.test(n)))`
e. Nothing downloadable: record it. Start the script in the background with `--record <duration + 15>`. When it prints `Rung 4e (record)`, play the tab from the start, at 1×, unmuted, at full volume:
   ```js
   const m = document.querySelector('video, audio');
   m.currentTime = 0; m.muted = false; m.volume = 1; m.playbackRate = 1; await m.play();
   ```
   Let it play until the `ended` event. Ask the user to keep system audio unmuted and quiet otherwise, because everything the speakers play is captured. If playback stalled, the transcript ends early. Rerun into a fresh folder with a larger margin.
f. `drm: true`, or the player reports encrypted media: stop and tell the user. Never circumvent DRM.

## Rules

- Never print, log, or write a signed URL (one carrying tokens in its query string) into chat, files, commands or artifacts. Move it only through the clipboard. The script prints just the host and length, and redacts the source from ffmpeg and yt-dlp errors.
- When Claude in Chrome blocks a URL, never work around it: no encoding, splitting, or moving it into the clipboard, files or downloads from page JavaScript. Only the user moves it, through the console.
- Never pass `--cookies-from-browser` to yt-dlp.
- If diarization fails on Hugging Face access, the script still finishes with `transcript_raw.md`. Tell the user to run `hf auth login` in their own terminal. Never handle tokens.
- Verify by reading only the first and last few lines of the transcript. Its last timestamp should be within a few minutes of `ffprobe`'s duration for `audio.wav`. Don't paste transcript content into chat unless asked.

## Outputs and resume

| File | Step |
|---|---|
| `audio.mka` | saved original audio (rungs 2, 3, 4e); a local file is used in place |
| `audio.wav` | mono 16 kHz, offset-corrected (`meeting-digest extract-audio`) |
| `transcript_raw.json` / `.md` | word-timed transcript (`transcribe`) |
| `speaker_turns.json` | speaker turns (`diarize`) |
| `transcript.json` / `.md` | speaker-labeled transcript (`label`) |

Rerunning the same command skips every step whose output exists. Downloads and recordings are written to `audio.part.mka` (yt-dlp uses `*.part`) and renamed only when complete, so a leftover `.part` file is just an interrupted download. To change the language or model, delete `transcript_raw.*` and the later outputs first.

For notes and screenshots, hand the recording to the `meeting-digest` skill. It needs the video; this skill keeps only the audio.
