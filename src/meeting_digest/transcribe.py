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
    body = "\n\n".join(f"[{stamp(s['start'])}–{stamp(s['end'])}] {s['text']}" for s in segments)
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
