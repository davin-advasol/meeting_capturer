from datetime import datetime

from app.formatting import seconds_to_mmss, format_transcript
from app.models import Segment, Transcript


def test_seconds_to_mmss():
    assert seconds_to_mmss(0) == "00:00"
    assert seconds_to_mmss(5) == "00:05"
    assert seconds_to_mmss(612.4) == "10:12"
    assert seconds_to_mmss(3661) == "61:01"


def _transcript():
    return Transcript(
        meeting_id="m1", source_file="a.mp4", duration_sec=20,
        provider="p", created_at=datetime(2026, 6, 15),
        speakers=["Speaker 1", "Speaker 2"],
        segments=[
            Segment(id=0, speaker="Speaker 1", start=0.0, end=4.0, text="Hello."),
            Segment(id=1, speaker="Speaker 2", start=4.5, end=9.0, text="Hi there."),
        ],
    )


def test_format_transcript_lines():
    text = format_transcript(_transcript())
    assert "[00:00] Speaker 1: Hello." in text
    assert "[00:04] Speaker 2: Hi there." in text
