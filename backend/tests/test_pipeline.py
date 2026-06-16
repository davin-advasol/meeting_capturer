import app.pipeline as pipeline_mod
from app.models import (
    JobStatus, Notes, Segment, TranscriptionResult,
)
from app.pipeline import run_pipeline
from app.storage import MeetingStorage


class FakeTranscriber:
    name = "fake"

    def transcribe(self, audio_path, language=None):
        return TranscriptionResult(
            provider="fake", language="en",
            segments=[
                Segment(id=0, speaker="Speaker 1", start=0, end=4, text="Hello."),
                Segment(id=1, speaker="Speaker 2", start=4, end=8, text="We ship Friday."),
            ],
        )


class _Structured:
    def invoke(self, messages):
        return Notes(summary="Shipping Friday.")


class FakeLLM:
    def with_structured_output(self, schema):
        return _Structured()


def _setup(tmp_path, monkeypatch, vad=False):
    store = MeetingStorage(tmp_path)
    mid = store.create_meeting("a.mp4", b"data", vad_trim=vad)
    monkeypatch.setattr(pipeline_mod, "extract_audio", lambda src, dest: 8.0)
    trims = {}
    monkeypatch.setattr(
        pipeline_mod, "trim_silence",
        lambda audio, dest, min_silence_sec: trims.setdefault("called", True),
    )
    return store, mid, trims


def test_pipeline_happy_path(tmp_path, monkeypatch):
    store, mid, _ = _setup(tmp_path, monkeypatch)
    run_pipeline(mid, store, FakeTranscriber(), FakeLLM(), "claude-x", vad_trim=False)

    job = store.load_job(mid)
    assert job.status == JobStatus.done and job.percent == 100
    transcript = store.load_transcript(mid)
    assert transcript.duration_sec == 8.0
    assert transcript.speakers == ["Speaker 1", "Speaker 2"]
    notes = store.load_notes(mid)
    assert notes.summary == "Shipping Friday."
    assert notes.model == "claude-x"
    assert "# a.mp4 — Notes" in store.load_notes_markdown(mid)


def test_pipeline_runs_vad_when_enabled(tmp_path, monkeypatch):
    store, mid, trims = _setup(tmp_path, monkeypatch, vad=True)
    run_pipeline(mid, store, FakeTranscriber(), FakeLLM(), "claude-x", vad_trim=True)
    assert trims.get("called") is True


def test_pipeline_marks_failed_on_error(tmp_path, monkeypatch):
    store, mid, _ = _setup(tmp_path, monkeypatch)

    class Boom:
        name = "boom"

        def transcribe(self, audio_path, language=None):
            raise RuntimeError("provider down")

    run_pipeline(mid, store, Boom(), FakeLLM(), "claude-x", vad_trim=False)
    job = store.load_job(mid)
    assert job.status == JobStatus.failed
    assert "provider down" in job.error
