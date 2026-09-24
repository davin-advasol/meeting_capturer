import types
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
    assert any(x["end"] > y["start"] for x, y in zip(turns, turns[1:], strict=False))
