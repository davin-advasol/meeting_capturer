from datetime import datetime

from app.models import ActionItem, Notes, Segment, TimelineEntry, Transcript
from app.notes.generator import generate_notes


class _FakeStructured:
    def __init__(self, result, captured):
        self._result = result
        self._captured = captured

    def invoke(self, messages):
        self._captured["messages"] = messages
        return self._result


class FakeLLM:
    def __init__(self, result):
        self._result = result
        self.captured = {}

    def with_structured_output(self, schema):
        assert schema is Notes
        return _FakeStructured(self._result, self.captured)


def _transcript():
    return Transcript(
        meeting_id="m1", source_file="a.mp4", duration_sec=20, provider="p",
        created_at=datetime(2026, 6, 15), speakers=["Speaker 1"],
        segments=[Segment(id=0, speaker="Speaker 1", start=0, end=4, text="We ship Friday.")],
    )


def test_generate_notes_returns_model_and_sends_transcript():
    expected = Notes(
        summary="We agreed to ship Friday.",
        action_items=[ActionItem(task="Ship", owner="Speaker 1", due="2026-06-19")],
        topic_timeline=[TimelineEntry(start=0.0, topic="Release")],
    )
    llm = FakeLLM(expected)
    notes = generate_notes(_transcript(), llm)
    assert notes.summary == "We agreed to ship Friday."
    # the transcript text reached the model
    sent = "".join(str(m) for m in llm.captured["messages"])
    assert "We ship Friday." in sent
