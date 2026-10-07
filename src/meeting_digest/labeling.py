"""Align word-timed transcript text with diarization turns.

Words that cannot be attributed confidently stay unattributed rather than
being guessed at — a wrong speaker label is worse than a missing one.
"""

from __future__ import annotations

import math

from meeting_digest.errors import DigestError

MERGE_GAP_SECONDS = 1.5
MAJORITY = 0.5


def validate_interval(row: dict) -> None:
    start, end = row.get("start"), row.get("end")
    numeric = all(isinstance(x, (int, float)) and math.isfinite(x) for x in (start, end))
    if not numeric or start < 0 or end < start:
        raise DigestError(f"Invalid time interval: {row}")


def speaker_for(word: dict, turns: list[dict]) -> str | None:
    """Return the diarization speaker that clearly owns this word, or None.

    None means either no overlap, less than half the word covered, or two
    speakers too close to separate.
    """
    overlap: dict[str, float] = {}
    duration = max(word["end"] - word["start"], 0.001)
    for turn in turns:
        shared = max(0.0, min(word["end"], turn["end"]) - max(word["start"], turn["start"]))
        if shared:
            key = turn["source_speaker"]
            overlap[key] = overlap.get(key, 0.0) + shared
    if not overlap:
        return None
    ranked = sorted(overlap.items(), key=lambda item: item[1], reverse=True)
    if ranked[0][1] < MAJORITY * duration:
        return None
    if len(ranked) > 1 and ranked[1][1] >= MAJORITY * ranked[0][1]:
        return None
    return ranked[0][0]


def label(raw: dict, diarization: dict) -> dict:
    """Combine a raw transcript and speaker turns into a labeled transcript."""
    turns = diarization["turns"]
    for turn in turns:
        validate_interval(turn)
    turns = sorted(turns, key=lambda t: (t["start"], t["end"]))

    words = []
    for segment in raw["segments"]:
        validate_interval(segment)
        if not segment.get("words"):
            raise DigestError("Word timestamps are required for reliable speaker alignment.")
        for word in segment["words"]:
            validate_interval(word)
            words.append(word)
    words.sort(key=lambda w: (w["start"], w["end"]))

    names: dict[str, str] = {}
    result: list[dict] = []
    for word in words:
        source = speaker_for(word, turns)
        if source is not None and source not in names:
            names[source] = f"Speaker {len(names) + 1}"
        speaker = names.get(source)
        mergeable = (
            result
            and result[-1]["speaker"] == speaker
            and word["start"] - result[-1]["end"] <= MERGE_GAP_SECONDS
        )
        if mergeable:
            result[-1]["end"] = max(result[-1]["end"], word["end"])
            result[-1]["text"] += word["text"]
        else:
            result.append(
                {
                    "start": word["start"],
                    "end": word["end"],
                    "speaker": speaker,
                    "text": word["text"].lstrip(),
                }
            )
    return {
        "source": raw["source"],
        "language": raw.get("language"),
        "backend": f"{raw['backend']} + {diarization['backend']}",
        "speakers": names,
        "segments": result,
        "note": "Null speaker means no reliable match or overlapping speakers.",
    }
