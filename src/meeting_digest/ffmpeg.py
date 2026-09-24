"""Every subprocess call to ffmpeg and ffprobe lives here.

Isolating them means the rest of the package is pure enough to unit-test.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

from meeting_digest.errors import DigestError

_REQUIRED_BINARIES = ("ffmpeg", "ffprobe")
_REQUIRED_MODULES = ("numpy", "cv2")


def dependencies() -> dict[str, bool]:
    """Report which external requirements are present."""
    found = {name: bool(shutil.which(name)) for name in _REQUIRED_BINARIES}
    found.update({name: importlib.util.find_spec(name) is not None for name in _REQUIRED_MODULES})
    return found


def require_dependencies() -> None:
    missing = [name for name, present in dependencies().items() if not present]
    if missing:
        raise DigestError(
            "Missing dependencies: "
            + ", ".join(missing)
            + ". FFmpeg and ffprobe are separate executables that must be on PATH; "
            "see the skill's references/setup.md."
        )


def run(args: list[str]) -> None:
    """Run a command, raising DigestError with its stderr on failure."""
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip()
        raise DigestError(f"{args[0]} failed: {detail}")


def probe(path: Path) -> dict:
    """Return ffprobe's JSON description of a media file."""
    if not path.is_file():
        raise DigestError(f"File does not exist: {path}")
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise DigestError(f"ffprobe could not read {path}: {result.stderr.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise DigestError(f"ffprobe returned unreadable output for {path}: {exc}") from None


def select_stream(probe_data: dict, codec_type: str) -> dict:
    """Return the first real stream of the given type, skipping cover art."""
    for stream in probe_data.get("streams", []):
        if stream.get("codec_type") != codec_type:
            continue
        if stream.get("disposition", {}).get("attached_pic"):
            continue
        return stream
    raise DigestError(f"Recording has no {codec_type} stream.")


def stream_gray_frames(
    video: Path, stream_index: int, filters: list[str], width: int, height: int
) -> Iterator[object]:
    """Yield grayscale frames decoded through the given filter chain.

    Frames arrive as raw bytes on a pipe and are reshaped into numpy arrays.
    An incomplete final frame is an error, not a silent truncation.
    """
    import numpy as np

    command = [
        "ffmpeg",
        "-v",
        "error",
        "-nostdin",
        "-noautorotate",
        "-i",
        str(video),
        "-map",
        f"0:{stream_index}",
        "-an",
        "-vf",
        ",".join(filters),
        "-f",
        "rawvideo",
        "-pix_fmt",
        "gray",
        "pipe:1",
    ]
    size = width * height
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors)
        try:
            while True:
                raw = bytearray()
                while len(raw) < size:
                    part = process.stdout.read(size - len(raw))
                    if not part:
                        break
                    raw.extend(part)
                if not raw:
                    break
                if len(raw) != size:
                    raise DigestError("ffmpeg produced an incomplete video frame.")
                yield np.frombuffer(bytes(raw), dtype=np.uint8).reshape(height, width)
            if process.wait():
                errors.seek(0)
                raise DigestError(errors.read().decode(errors="replace").strip())
        finally:
            if process.stdout is not None:
                process.stdout.close()
            if process.poll() is None:
                process.kill()
                process.wait()
