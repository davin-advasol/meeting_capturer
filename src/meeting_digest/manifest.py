"""The artifact formats both skills depend on: writing and checking them.

The contract these functions enforce is documented for skill authors in
skills/meeting-digest/references/artifacts.md.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from meeting_digest.errors import DigestError

TIMESTAMP_BASIS = "seconds relative to container start; sampled times approximate"


def write_json(path: Path, data: dict, *, ensure_ascii: bool = True) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=ensure_ascii), encoding="utf-8")
    return path


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DigestError(f"{path} is not valid JSON: {exc}") from None


def build_frames_manifest(
    source: str, duration: float, sampled: int, settings: dict, choices: list[dict]
) -> dict:
    """Assign ids and relative paths to selected timestamps."""
    frames = []
    for position, choice in enumerate(choices, 1):
        name = f"frame-{position:05d}-{choice['timestamp']:.3f}s.png"
        frames.append(
            {
                **choice,
                "id": f"frame-{position:05d}",
                "path": f"frames/{name}",
                "inspected": False,
            }
        )
    return {
        "source": source,
        "duration": duration,
        "timestamp_basis": TIMESTAMP_BASIS,
        "sampled_frames": sampled,
        "settings": settings,
        "frames": frames,
    }


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def _check_frames(directory: Path, problems: list[str]) -> None:
    path = directory / "frames.json"
    if not path.is_file():
        return
    data = read_json(path)
    for key in ("source", "duration", "frames"):
        if key not in data:
            problems.append(f"frames.json is missing the required key {key!r}")
    seen: set[str] = set()
    for frame in data.get("frames", []):
        frame_id = frame.get("id", "<no id>")
        if frame_id in seen:
            problems.append(f"frames.json has a duplicate frame id: {frame_id}")
        seen.add(frame_id)
        if not _finite(frame.get("timestamp")) or frame["timestamp"] < 0:
            problems.append(f"{frame_id} has a non-finite or negative timestamp")
        relative = frame.get("path")
        if not relative:
            problems.append(f"{frame_id} has no path")
        elif not (directory / relative).is_file():
            problems.append(f"{frame_id} points at a missing image: {relative}")
        elif (directory / relative).stat().st_size == 0:
            problems.append(f"{frame_id} points at an empty image: {relative}")


def _check_intervals(path: Path, rows_key: str, problems: list[str]) -> None:
    if not path.is_file():
        return
    data = read_json(path)
    for row in data.get(rows_key, []):
        start, end = row.get("start"), row.get("end")
        if not _finite(start) or not _finite(end) or start < 0 or end < start:
            problems.append(f"{path.name} contains an invalid interval: {start} to {end}")
            break


def _check_sources_agree(directory: Path, problems: list[str]) -> None:
    transcript = directory / "transcript.json"
    turns = directory / "speaker_turns.json"
    if not (transcript.is_file() and turns.is_file()):
        return
    if read_json(transcript).get("source") != read_json(turns).get("source"):
        problems.append("transcript.json and speaker_turns.json must come from the same audio file")


def validate_meeting(directory: Path) -> list[str]:
    """Check a meeting directory against the artifact contract.

    Returns a list of problems; an empty list means the directory is valid.
    Missing optional artifacts are not problems — a meeting with only frames
    is a legitimate partial ingestion.
    """
    problems: list[str] = []
    if not directory.is_dir():
        return [f"Meeting directory does not exist: {directory}"]
    _check_frames(directory, problems)
    _check_intervals(directory / "transcript.json", "segments", problems)
    _check_intervals(directory / "speaker_turns.json", "turns", problems)
    _check_sources_agree(directory, problems)
    if not any((directory / name).exists() for name in ("frames.json", "transcript.json")):
        problems.append(
            f"{directory} contains no frames.json or transcript.json; nothing was ingested here"
        )
    return problems


def mark_inspected(directory: Path, frame_ids: list[str]) -> int:
    """Set `inspected` to true for the named frames. Returns how many changed.

    This records only that a human previously reviewed the frame — it does
    not mean the image is in any model's context.
    """
    path = directory / "frames.json"
    if not path.is_file():
        raise DigestError(f"No frames.json in {directory}")
    data = read_json(path)
    known = {frame.get("id") for frame in data.get("frames", [])}
    unknown = [frame_id for frame_id in frame_ids if frame_id not in known]
    if unknown:
        raise DigestError(f"Unknown frame ids: {', '.join(unknown)}")
    changed = 0
    for frame in data["frames"]:
        if frame["id"] in frame_ids and not frame.get("inspected"):
            frame["inspected"] = True
            changed += 1
    write_json(path, data)
    return changed
