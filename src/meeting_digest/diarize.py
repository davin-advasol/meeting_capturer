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


def has_overlaps(turns: list[dict]) -> bool:
    """Whether any turn runs past the start of the next one.

    Assumes `turns` is sorted by (start, end). Overlapping speech is preserved
    in the artifact even though the readable transcript cannot attribute the
    overlapping words, so consumers need to know it is present.
    """
    return any(x["end"] > y["start"] for x, y in zip(turns, turns[1:], strict=False))


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
        "has_overlaps": has_overlaps(turns),
    }
