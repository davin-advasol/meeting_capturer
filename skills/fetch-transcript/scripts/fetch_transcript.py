"""Turn a recording link or file into a local transcript.

Source ladder, cheapest rung first; the first rung that yields audio wins:
  1. local file        -> used as is
  2. direct media URL  -> ffprobe finds an audio stream; the audio is stream-copied
  3. page URL          -> yt-dlp, best audio only (never with browser cookies)
If all three fail the script exits with code 3 and the agent takes over in the
browser (see SKILL.md), then reruns with a media URL, the clipboard, or --record.

The meeting-digest CLI does the rest: extract-audio -> transcribe -> diarize ->
label. A step is skipped when its output exists, and downloads are written
under a .part name first, so a rerun resumes and an interrupted download never
looks complete.

Usage, from the repo root:
  py skills/fetch-transcript/scripts/fetch_transcript.py meetings/<date>-<slug> [SOURCE]
SOURCE defaults to the clipboard, so a signed URL never lands in shell history or
logs. Exit codes: 0 done, 1 failed, 2 bad input, 3 needs the browser rung.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

NEEDS_BROWSER = 3


def clipboard() -> str:
    import tkinter

    root = tkinter.Tk()
    root.withdraw()
    try:
        return root.clipboard_get().strip()
    except tkinter.TclError:  # empty, or not text
        return ""
    finally:
        root.destroy()


def is_url(text: str) -> bool:
    parts = urlsplit(text)
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def describe(text: str) -> str:
    """Summarise a source without revealing it."""
    if is_url(text):
        return f"http(s) URL, host {urlsplit(text).hostname}, length {len(text)}"
    if text and Path(text).is_file():
        return f"local file, length {len(text)}"
    return f"no URL or file (length {len(text)})"


def redact(text: str, source: str) -> str:
    """ffmpeg and yt-dlp echo their input; keep signed URLs out of the output."""
    return text.replace(source, "<source>").strip()


def has_audio(url: str) -> bool:
    command = ["ffprobe", "-v", "error", "-rw_timeout", "20000000", "-select_streams", "a"]
    command += ["-show_entries", "stream=index", "-of", "csv=p=0", url]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0 and bool(result.stdout.strip())


def stream_copy(url: str, saved: Path) -> None:
    part = saved.with_name("audio.part.mka")
    command = ["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", url]
    command += ["-map", "0:a:0", "-vn", "-c", "copy", str(part)]  # Matroska takes any codec
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        part.unlink(missing_ok=True)
        sys.exit("ffmpeg failed: " + redact(result.stderr, url))
    part.replace(saved)


def yt_dlp(url: str, saved: Path) -> bool:
    # --ignore-config keeps a user config from adding --cookies-from-browser.
    command = [sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-playlist", "--quiet"]
    command += ["--no-warnings", "-f", "bestaudio/best", "--remux-video", "mka"]
    command += ["-o", str(saved.with_suffix(".%(ext)s")), url]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode or not saved.is_file():
        reason = redact(result.stderr, url).splitlines()
        print("  yt-dlp:", reason[-1] if reason else f"exit {result.returncode}")
        return False
    return True


def acquire(source: str, saved: Path) -> Path | None:
    """Walk rungs 1-3. Returns the audio to use, or None when the browser must take over."""
    if Path(source).is_file():
        print("Rung 1 (local file)")
        return Path(source)
    if has_audio(source):
        print(f"Rung 2 (direct media): copying the audio to {saved} ...", flush=True)
        stream_copy(source, saved)
        return saved
    print("Rung 2 (direct media): no audio stream found", flush=True)
    if yt_dlp(source, saved):
        print(f"Rung 3 (yt-dlp): saved {saved}")
        return saved
    print("Rung 3 (yt-dlp): no audio")
    return None


def record(seconds: float, saved: Path) -> None:
    """Rung 4e: capture what the speakers play (WASAPI loopback) into FLAC."""
    import soundcard

    rate = 48000
    speaker = soundcard.default_speaker()
    loopback = soundcard.get_microphone(id=str(speaker.name), include_loopback=True)
    part = saved.with_name("audio.part.mka")
    encoder = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-nostdin", "-y", "-f", "f32le", "-ar", str(rate), "-ac", "1"]
        + ["-i", "pipe:0", "-c:a", "flac", str(part)],
        stdin=subprocess.PIPE,
    )
    print(f"Rung 4e (record): {seconds:g} s from {speaker.name}", flush=True)
    # soundcard pads gaps where nothing plays with zeros, so the timeline stays real.
    with loopback.recorder(samplerate=rate, channels=1) as recorder:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            encoder.stdin.write(recorder.record(numframes=rate // 2).astype("<f4").tobytes())
    encoder.stdin.close()
    if encoder.wait():
        part.unlink(missing_ok=True)
        sys.exit("ffmpeg could not encode the recording")
    part.replace(saved)


def digest(*args: object) -> bool:
    command = [sys.executable, "-m", "meeting_digest.cli", *map(str, args)]
    return subprocess.run(command).returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("meeting", type=Path, nargs="?", help="output folder")
    parser.add_argument("source", nargs="?", help="file, media URL or page URL (default: clipboard)")
    parser.add_argument("--peek", action="store_true", help="describe the clipboard and exit")
    parser.add_argument("--record", type=float, metavar="SECONDS", help="record system audio")
    parser.add_argument("--model", default="small", help="faster-whisper model (default: small)")
    parser.add_argument("--language", help="e.g. de or en (default: auto-detect)")
    parser.add_argument("--no-speakers", action="store_true", help="skip speaker labels")
    args = parser.parse_args()
    sys.stdout.reconfigure(line_buffering=True)  # progress shows up live in logs

    if args.peek:
        print("clipboard:", describe(clipboard()))
        return 0
    if args.meeting is None:
        parser.error("the meeting folder is required")
    started = time.monotonic()
    meeting = args.meeting
    meeting.mkdir(parents=True, exist_ok=True)
    saved, wav = meeting / "audio.mka", meeting / "audio.wav"

    if not wav.exists():
        if saved.exists():
            print(f"Reusing {saved}")
            audio = saved
        elif args.record:
            record(args.record, saved)
            audio = saved
        else:
            source = args.source
            if source is None:
                source = clipboard()
                print("clipboard:", describe(source))
            if not (is_url(source) or Path(source).is_file()):
                print("error: source is neither a file nor an http(s) URL", file=sys.stderr)
                return 2
            audio = acquire(source, saved)
            if audio is None:
                print(
                    "No audio from rungs 1-3: use the browser rung in SKILL.md, then rerun "
                    "with the media URL, the clipboard, or --record SECONDS.",
                    file=sys.stderr,
                )
                return NEEDS_BROWSER
        if not digest("extract-audio", audio, wav):
            return 1

    raw = meeting / "transcript_raw.json"
    if not raw.exists():
        language = ["--language", args.language] if args.language else []
        if not digest("transcribe", wav, meeting, "--model", args.model, *language):
            return 1

    result = meeting / "transcript_raw.md"
    if not args.no_speakers:
        turns = meeting / "speaker_turns.json"
        if turns.exists() or digest("diarize", wav, turns):
            if (meeting / "transcript.json").exists() or digest("label", raw, turns, meeting):
                result = meeting / "transcript.md"
        else:
            print(
                "Speaker labels skipped: diarization failed. If the error mentions Hugging "
                "Face access, run `hf auth login` in your own terminal, then rerun.",
                file=sys.stderr,
            )

    print(f"Done in {time.monotonic() - started:.0f} s: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
