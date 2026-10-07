"""Each command's end-to-end work: read inputs, call modules, write artifacts."""

from __future__ import annotations

from pathlib import Path

from meeting_digest import diarize as diarize_module
from meeting_digest import transcribe as transcribe_module
from meeting_digest.errors import DigestError
from meeting_digest.ffmpeg import probe, run, select_stream
from meeting_digest.frames import ScanSettings, scan
from meeting_digest.labeling import label
from meeting_digest.manifest import build_frames_manifest, read_json, write_json
from meeting_digest.timeline import container_duration, stamp, stream_offset


def select_frames(
    video: Path,
    output: Path,
    settings: ScanSettings,
    crop: tuple[int, int, int, int] | None,
    timestamps: list[float] | None,
    settings_record: dict,
) -> Path:
    """Scan or extract at explicit times, then save full-resolution PNGs."""
    if (output / "frames.json").exists() or (output / "frames").exists():
        raise DigestError("Frame outputs already exist; use a fresh output directory.")
    data = probe(video)
    stream = select_stream(data, "video")
    offset = stream_offset(data, stream, clamp=True)
    duration = container_duration(data, stream)

    if timestamps is not None:
        out_of_range = [t for t in timestamps if t < offset or t >= duration]
        if out_of_range:
            raise DigestError(
                f"Timestamps outside the video timeline ({offset:.3f}–{duration:.3f}s): "
                + ", ".join(f"{t:g}" for t in out_of_range)
            )
        choices = [
            {"timestamp": t, "reason": "requested", "approximate_change_start": None}
            for t in timestamps
        ]
        sampled = 0
    else:
        choices, sampled = scan(video, stream, offset, settings, crop)

    if not choices:
        raise DigestError("No frames decoded.")

    manifest = build_frames_manifest(
        str(video.resolve()), duration, sampled, settings_record, choices
    )
    (output / "frames").mkdir(parents=True)
    for frame in manifest["frames"]:
        target = output / frame["path"]
        run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-nostdin",
                "-n",
                "-ss",
                str(frame["timestamp"]),
                "-noautorotate",
                "-i",
                str(video),
                "-map",
                f"0:{stream['index']}",
                "-frames:v",
                "1",
                "-update",
                "1",
                str(target),
            ]
        )
        if not target.is_file() or target.stat().st_size == 0:
            raise DigestError(
                f"No image produced at {frame['timestamp']}; no complete manifest written."
            )
    return write_json(output / "frames.json", manifest)


def write_transcript(audio: Path, output: Path, **options) -> Path:
    targets = [output / "transcript_raw.json", output / "transcript_raw.md"]
    if any(target.exists() for target in targets):
        raise DigestError("Transcript exists; choose a new output directory.")
    result = transcribe_module.transcribe(audio, **options)
    write_json(targets[0], result, ensure_ascii=False)
    targets[1].write_text(transcribe_module.render_markdown(result["segments"]), encoding="utf-8")
    return targets[0]


def write_speaker_turns(audio: Path, output: Path, **options) -> Path:
    if output.exists():
        raise DigestError(f"Output already exists; choose a new path: {output}")
    return write_json(output, diarize_module.diarize(audio, **options))


def write_labeled_transcript(raw_path: Path, turns_path: Path, output: Path) -> Path:
    targets = [output / "transcript.json", output / "transcript.md"]
    if any(target.exists() for target in targets):
        raise DigestError("Labeled transcript already exists; choose a new output directory.")
    raw = read_json(raw_path)
    diarization = read_json(turns_path)
    if Path(raw["source"]).resolve() != Path(diarization["source"]).resolve():
        raise DigestError("Transcript and speaker turns come from different audio files.")
    result = label(raw, diarization)
    write_json(targets[0], result, ensure_ascii=False)
    body = "\n\n".join(
        f"[{stamp(s['start'])}–{stamp(s['end'])}] "
        f"{s['speaker'] or 'Speaker uncertain'}: {s['text']}"
        for s in result["segments"]
    )
    targets[1].write_text("# Transcript\n\n" + body, encoding="utf-8")
    return targets[0]
