import pytest

from app.config import Settings
from app.models import Notes, Segment, TranscriptionResult


class FakeTranscriber:
    name = "fake"

    def transcribe(self, audio_path, language=None):
        return TranscriptionResult(
            provider="fake", language="en",
            segments=[Segment(id=0, speaker="Speaker 1", start=0, end=4, text="Hello.")],
        )


class _Structured:
    def invoke(self, messages):
        return Notes(summary="A summary.")


class FakeLLM:
    def with_structured_output(self, schema):
        return _Structured()

    def invoke(self, messages):
        class _R:
            content = "A fake answer."
        return _R()


@pytest.fixture
def test_settings(tmp_path):
    return Settings(
        data_dir=str(tmp_path / "data"),
        transcriber_provider="openai", openai_api_key="sk-test",
        llm_provider="anthropic", anthropic_api_key="sk-ant",
        llm_model="claude-test",
    )
