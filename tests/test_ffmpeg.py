from pathlib import Path

import pytest

from meeting_digest.errors import DigestError
from meeting_digest.ffmpeg import dependencies, run, select_stream


def test_dependencies_reports_the_four_requirements():
    assert set(dependencies()) == {"ffmpeg", "ffprobe", "numpy", "cv2"}


def test_dependencies_values_are_booleans():
    assert all(isinstance(v, bool) for v in dependencies().values())


def test_select_stream_returns_the_first_matching_stream():
    data = {
        "streams": [
            {"codec_type": "audio", "index": 0},
            {"codec_type": "video", "index": 1},
        ]
    }
    assert select_stream(data, "video")["index"] == 1


def test_select_stream_skips_attached_cover_art():
    data = {
        "streams": [
            {"codec_type": "video", "index": 0, "disposition": {"attached_pic": 1}},
            {"codec_type": "video", "index": 1},
        ]
    }
    assert select_stream(data, "video")["index"] == 1


def test_select_stream_raises_when_nothing_matches():
    with pytest.raises(DigestError, match="no audio stream"):
        select_stream({"streams": [{"codec_type": "video", "index": 0}]}, "audio")


def test_run_raises_digest_error_with_the_stderr_text():
    with pytest.raises(DigestError) as exc:
        run(["ffmpeg", "-v", "error", "-i", str(Path("does-not-exist.mp4")), "-f", "null", "-"])
    assert "does-not-exist.mp4" in str(exc.value)
