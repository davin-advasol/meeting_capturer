"""Timestamp formatting and audio/video stream offset arithmetic.

Both concerns used to be duplicated across the scripts, and the two copies of
the offset calculation disagreed about negative offsets. `clamp` makes that
difference explicit instead of accidental.
"""

from __future__ import annotations

from meeting_digest.errors import DigestError


def stamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS.mmm."""
    ms = round(seconds * 1000)
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02}.{ms % 1000:03}"


def stream_offset(probe_data: dict, stream: dict, *, clamp: bool) -> float:
    """Return a stream's start time relative to the container origin.

    A positive result means the stream starts after the container. Audio
    extraction needs the signed value so it can pad or trim; frame scanning
    uses it as a timeline base, where a negative value is meaningless, so it
    passes `clamp=True`.
    """
    origin = float(probe_data.get("format", {}).get("start_time", 0))
    offset = float(stream.get("start_time", origin)) - origin
    return max(0.0, offset) if clamp else offset


def container_duration(probe_data: dict, stream: dict) -> float:
    """Return the media duration in seconds.

    Some containers — fragmented MP4, certain MKV files — omit
    `format.duration`. Fall back to the stream's own duration before failing.
    """
    for source in (probe_data.get("format", {}), stream):
        value = source.get("duration")
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    raise DigestError(
        "Could not determine the recording duration: neither the container nor the "
        "stream reports one. Try remuxing with `ffmpeg -i <input> -c copy <output>.mp4`."
    )
