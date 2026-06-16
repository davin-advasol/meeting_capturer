from datetime import datetime

from app.models import (
    ActionItem, Job, JobStatus, QAEntry, Segment, StoredNotes, Transcript,
)
from app.storage import MeetingStorage


def test_create_meeting_writes_source_and_job(tmp_path):
    store = MeetingStorage(tmp_path)
    mid = store.create_meeting("weekly sync.mp4", b"\x00\x01\x02", vad_trim=True)
    assert (store.meeting_dir(mid) / "source" / "weekly sync.mp4").read_bytes() == b"\x00\x01\x02"
    job = store.load_job(mid)
    assert job.meeting_id == mid
    assert job.vad_trim is True
    assert job.status == JobStatus.pending
    assert job.source_file == "weekly sync.mp4"


def test_job_roundtrip(tmp_path):
    store = MeetingStorage(tmp_path)
    mid = store.create_meeting("a.mp4", b"x", vad_trim=False)
    job = store.load_job(mid)
    job.status = JobStatus.transcribing
    job.percent = 30
    store.save_job(job)
    assert store.load_job(mid).percent == 30


def test_transcript_roundtrip(tmp_path):
    store = MeetingStorage(tmp_path)
    mid = store.create_meeting("a.mp4", b"x", vad_trim=False)
    t = Transcript(
        meeting_id=mid, source_file="a.mp4", duration_sec=10, provider="p",
        created_at=datetime(2026, 6, 15), speakers=["Speaker 1"],
        segments=[Segment(id=0, speaker="Speaker 1", start=0, end=1, text="hi")],
    )
    store.save_transcript(t)
    assert store.load_transcript(mid).segments[0].text == "hi"


def test_notes_and_markdown(tmp_path):
    store = MeetingStorage(tmp_path)
    mid = store.create_meeting("a.mp4", b"x", vad_trim=False)
    sn = StoredNotes(
        summary="s", meeting_id=mid, model="claude-opus-4-8",
        generated_at=datetime(2026, 6, 15),
        action_items=[ActionItem(task="do x")],
    )
    store.save_notes(sn)
    store.save_notes_markdown(mid, "# Notes\n")
    assert store.load_notes(mid).summary == "s"
    assert store.load_notes_markdown(mid) == "# Notes\n"


def test_qa_append(tmp_path):
    store = MeetingStorage(tmp_path)
    mid = store.create_meeting("a.mp4", b"x", vad_trim=False)
    assert store.load_qa(mid) == []
    store.append_qa(mid, QAEntry(question="q1", answer="a1"))
    store.append_qa(mid, QAEntry(question="q2", answer="a2"))
    qa = store.load_qa(mid)
    assert [e.question for e in qa] == ["q1", "q2"]


def test_exists(tmp_path):
    store = MeetingStorage(tmp_path)
    assert store.exists("nope") is False
    mid = store.create_meeting("a.mp4", b"x", vad_trim=False)
    assert store.exists(mid) is True
