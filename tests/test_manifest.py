import json

import pytest

from meeting_digest.errors import DigestError
from meeting_digest.manifest import (
    build_frames_manifest,
    mark_inspected,
    validate_meeting,
    write_json,
)


def make_meeting(tmp_path, frames=None):
    directory = tmp_path / "meeting"
    (directory / "frames").mkdir(parents=True)
    frames = (
        frames
        if frames is not None
        else [
            {
                "id": "frame-00001",
                "timestamp": 0.0,
                "reason": "initial",
                "approximate_change_start": None,
                "path": "frames/frame-00001-0.000s.png",
                "inspected": False,
            }
        ]
    )
    for frame in frames:
        (directory / frame["path"]).write_bytes(b"\x89PNG\r\n\x1a\n")
    write_json(
        directory / "frames.json",
        {
            "source": "/tmp/a.mp4",
            "duration": 10.0,
            "timestamp_basis": "seconds relative to container start",
            "sampled_frames": 20,
            "settings": {},
            "frames": frames,
        },
    )
    return directory


def test_write_json_creates_parents_and_writes_utf8(tmp_path):
    target = write_json(tmp_path / "a" / "b.json", {"text": "Grüße"}, ensure_ascii=False)
    assert json.loads(target.read_text(encoding="utf-8"))["text"] == "Grüße"


def test_build_frames_manifest_assigns_ids_and_paths():
    choices = [
        {"timestamp": 0.0, "reason": "initial", "approximate_change_start": None},
        {"timestamp": 1.25, "reason": "settled_change", "approximate_change_start": 1.0},
    ]
    manifest = build_frames_manifest("/tmp/a.mp4", 10.0, 20, {}, choices)
    assert manifest["frames"][0]["id"] == "frame-00001"
    assert manifest["frames"][1]["path"] == "frames/frame-00002-1.250s.png"
    assert manifest["frames"][1]["inspected"] is False


def test_validate_accepts_a_well_formed_meeting(tmp_path):
    assert validate_meeting(make_meeting(tmp_path)) == []


def test_validate_reports_a_missing_png(tmp_path):
    directory = make_meeting(tmp_path)
    (directory / "frames" / "frame-00001-0.000s.png").unlink()
    problems = validate_meeting(directory)
    assert any("frame-00001" in p for p in problems)


def test_validate_reports_a_negative_timestamp(tmp_path):
    directory = make_meeting(tmp_path)
    data = json.loads((directory / "frames.json").read_text(encoding="utf-8"))
    data["frames"][0]["timestamp"] = -1.0
    write_json(directory / "frames.json", data)
    assert any("timestamp" in p for p in validate_meeting(directory))


def test_validate_reports_duplicate_frame_ids(tmp_path):
    frames = [
        {
            "id": "frame-00001",
            "timestamp": 0.0,
            "reason": "initial",
            "approximate_change_start": None,
            "path": "frames/frame-00001-0.000s.png",
            "inspected": False,
        },
        {
            "id": "frame-00001",
            "timestamp": 1.0,
            "reason": "coverage",
            "approximate_change_start": None,
            "path": "frames/frame-00002-1.000s.png",
            "inspected": False,
        },
    ]
    assert any("duplicate" in p.lower() for p in validate_meeting(make_meeting(tmp_path, frames)))


def test_validate_reports_a_missing_directory(tmp_path):
    assert any("does not exist" in p for p in validate_meeting(tmp_path / "nope"))


def test_validate_reports_mismatched_transcript_sources(tmp_path):
    directory = make_meeting(tmp_path)
    write_json(directory / "transcript.json", {"source": "/tmp/a.wav", "segments": []})
    write_json(directory / "speaker_turns.json", {"source": "/tmp/b.wav", "turns": []})
    assert any("same audio" in p for p in validate_meeting(directory))


def test_mark_inspected_sets_the_flag(tmp_path):
    directory = make_meeting(tmp_path)
    assert mark_inspected(directory, ["frame-00001"]) == 1
    data = json.loads((directory / "frames.json").read_text(encoding="utf-8"))
    assert data["frames"][0]["inspected"] is True


def test_mark_inspected_rejects_an_unknown_id(tmp_path):
    with pytest.raises(DigestError, match="frame-99999"):
        mark_inspected(make_meeting(tmp_path), ["frame-99999"])
