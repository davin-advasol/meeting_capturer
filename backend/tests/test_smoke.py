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
