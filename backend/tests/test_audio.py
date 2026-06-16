import shutil
import subprocess
import wave

import pytest

from app.audio import concat_speech, extract_audio


def test_concat_speech_keeps_only_speech_regions():
    samples = list(range(20))  # 0..19
    # keep [2,5) and [10,13)
    timestamps = [{"start": 2, "end": 5}, {"start": 10, "end": 13}]
    assert concat_speech(samples, timestamps) == [2, 3, 4, 10, 11, 12]


def test_concat_speech_empty_returns_all():
    samples = [9, 8, 7]
    assert concat_speech(samples, []) == [9, 8, 7]


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
