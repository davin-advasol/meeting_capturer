"""Extract meeting audio while preserving its position on the video timeline."""

from __future__ import annotations

from pathlib import Path

from meeting_digest.errors import DigestError
from meeting_digest.ffmpeg import probe, run, select_stream
from meeting_digest.timeline import stream_offset


def build_filters(offset: float) -> list[str]:
    """Return the ffmpeg audio filter chain for a given stream offset.

    Audio that starts late is padded with silence; audio that starts early is
    trimmed. Either way the result begins at the video's zero, so transcript
    timestamps line up with extracted frames.
    """
    filters = ["asetpts=PTS-STARTPTS"]
    if offset > 0:
        filters.append(f"adelay={round(offset * 1000)}:all=1")
    elif offset < 0:
        filters.extend([f"atrim=start={-offset}", "asetpts=PTS-STARTPTS"])
    return filters


def extract_audio(video: Path, output: Path) -> Path:
    """Write mono 16 kHz PCM audio, offset-corrected to the video timeline."""
    if output.exists():
        raise DigestError(f"Output already exists; choose a new path: {output}")
    data = probe(video)
    stream = select_stream(data, "audio")
    filters = build_filters(stream_offset(data, stream, clamp=False))
    output.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-n",
            "-i",
            str(video),
            "-map",
            "0:a:0",
            "-vn",
            "-af",
            ",".join(filters),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(output),
        ]
    )
    return output
