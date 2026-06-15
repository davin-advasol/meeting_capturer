from datetime import datetime

from app.models import (
    ActionItem, Job, JobStatus, Notes, Segment, StoredNotes,
    TimelineEntry, Transcript, TranscriptionResult, QAEntry,
)


def test_transcript_roundtrip():
    t = Transcript(
        meeting_id="m1", source_file="a.mp4", duration_sec=12.5,
        language="en", provider="openai:gpt-4o-transcribe-diarize",
        created_at=datetime(2026, 6, 15, 10, 0, 0), speakers=["Speaker 1"],
        segments=[Segment(id=0, speaker="Speaker 1", start=0.0, end=4.2, text="Hi")],
    )
    dumped = t.model_dump_json()
    again = Transcript.model_validate_json(dumped)
    assert again.segments[0].text == "Hi"


def test_notes_defaults_to_empty_lists():
    n = Notes(summary="s")
    assert n.action_items == [] and n.decisions == []
    assert n.topic_timeline == [] and n.open_questions == []


def test_stored_notes_extends_notes():
    sn = StoredNotes(
        summary="s", meeting_id="m1", model="claude-opus-4-8",
        generated_at=datetime(2026, 6, 15),
        action_items=[ActionItem(task="do x", owner="Speaker 1", due=None)],
        topic_timeline=[TimelineEntry(start=0.0, topic="Intro")],
    )
    assert sn.meeting_id == "m1"
    assert sn.action_items[0].owner == "Speaker 1"


def test_job_status_enum_and_defaults():
    j = Job(meeting_id="m1", source_file="a.mp4", vad_trim=True,
            created_at=datetime(2026, 6, 15), updated_at=datetime(2026, 6, 15))
    assert j.status == JobStatus.pending and j.percent == 0


def test_qa_entry():
    q = QAEntry(question="q?", answer="a.")
    assert q.citations == []