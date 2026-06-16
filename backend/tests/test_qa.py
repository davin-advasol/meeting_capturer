from datetime import datetime

from app.models import QAEntry, Segment, Transcript
from app.qa.answerer import answer_question


class _Resp:
    def __init__(self, content):
        self.content = content


class FakeChat:
    def __init__(self, answer):
        self._answer = answer
        self.captured = {}

    def invoke(self, messages):
        self.captured["messages"] = messages
        return _Resp(self._answer)


def _transcript():
    return Transcript(
        meeting_id="m1", source_file="a.mp4", duration_sec=20, provider="p",
        created_at=datetime(2026, 6, 15), speakers=["Speaker 1"],
        segments=[Segment(id=0, speaker="Speaker 1", start=0, end=4, text="Budget is approved.")],
    )


def test_answer_question_returns_entry_with_transcript_context():
    chat = FakeChat("Yes, the budget was approved.")
    entry = answer_question(_transcript(), "Was the budget approved?", [], chat)
    assert isinstance(entry, QAEntry)
    assert entry.question == "Was the budget approved?"
    assert entry.answer == "Yes, the budget was approved."
    sent = "".join(str(m) for m in chat.captured["messages"])
    assert "Budget is approved." in sent


def test_answer_question_includes_history():
    chat = FakeChat("Follow-up answer.")
    history = [QAEntry(question="Q1?", answer="A1.")]
    answer_question(_transcript(), "Q2?", history, chat)
    sent = "".join(str(m) for m in chat.captured["messages"])
    assert "Q1?" in sent and "A1." in sent
