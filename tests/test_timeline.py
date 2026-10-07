import pytest

from meeting_digest.errors import DigestError
from meeting_digest.timeline import container_duration, stamp, stream_offset


def test_stamp_formats_hours_minutes_seconds_milliseconds():
    assert stamp(0) == "00:00:00.000"
    assert stamp(1.5) == "00:00:01.500"
    assert stamp(61.25) == "00:01:01.250"
    assert stamp(3723.004) == "01:02:03.004"


def test_stamp_rounds_to_the_nearest_millisecond():
    assert stamp(1.23456) == "00:00:01.235"


def _probe(format_start, stream_start):
    data = {"format": {"start_time": format_start, "duration": "10.0"}, "streams": []}
    stream = {} if stream_start is None else {"start_time": stream_start}
    return data, stream


def test_stream_offset_is_zero_when_streams_are_aligned():
    data, stream = _probe("0.0", "0.0")
    assert stream_offset(data, stream, clamp=False) == 0.0


def test_stream_offset_is_positive_when_the_stream_starts_late():
    data, stream = _probe("0.0", "0.5")
    assert stream_offset(data, stream, clamp=False) == pytest.approx(0.5)


def test_stream_offset_is_negative_when_the_stream_starts_early():
    data, stream = _probe("0.5", "0.0")
    assert stream_offset(data, stream, clamp=False) == pytest.approx(-0.5)


def test_stream_offset_clamps_negatives_when_asked():
    data, stream = _probe("0.5", "0.0")
    assert stream_offset(data, stream, clamp=True) == 0.0


def test_stream_offset_falls_back_to_the_container_origin():
    data, stream = _probe("0.25", None)
    assert stream_offset(data, stream, clamp=False) == 0.0


def test_container_duration_prefers_the_format_value():
    data = {"format": {"duration": "12.5"}}
    assert container_duration(data, {"duration": "99"}) == pytest.approx(12.5)


def test_container_duration_falls_back_to_the_stream():
    data = {"format": {}}
    assert container_duration(data, {"duration": "12.5"}) == pytest.approx(12.5)


def test_container_duration_raises_when_neither_is_present():
    with pytest.raises(DigestError, match="duration"):
        container_duration({"format": {}}, {})
