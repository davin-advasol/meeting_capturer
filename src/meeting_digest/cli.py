"""Command-line front door. Parses arguments and dispatches to the modules."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from meeting_digest import __version__
from meeting_digest.diarize import DEFAULT_MODEL
from meeting_digest.errors import DigestError
from meeting_digest.ffmpeg import dependencies, require_dependencies

if TYPE_CHECKING:
    # Only evaluated by type checkers; never imported at runtime. frames.py
    # imports cv2/numpy at module scope, and `check` must work without them.
    from meeting_digest.frames import ScanSettings

_SCAN_FLOATS = (
    "sample_fps",
    "stable_seconds",
    "motion_interval",
    "max_gap",
    "pixel_threshold",
    "change_ratio",
    "tile_ratio",
)


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meeting-digest",
        description="Turn recorded meetings into transcripts, screenshots, and notes.",
    )
    parser.add_argument("--version", action="version", version=f"meeting-digest {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    sub.add_parser("check", help="Report whether FFmpeg, ffprobe, numpy and cv2 are available")

    audio = sub.add_parser("extract-audio", help="Extract offset-corrected mono 16 kHz WAV")
    audio.add_argument("video", type=Path)
    audio.add_argument("output", type=Path)

    frames = sub.add_parser("frames", help="Select screenshot candidates locally")
    frames.add_argument("video", type=Path)
    frames.add_argument("output", type=Path)
    frames.add_argument("--sample-fps", type=float, default=2)
    frames.add_argument("--stable-seconds", type=float, default=1)
    frames.add_argument("--motion-interval", type=float, default=5)
    frames.add_argument("--max-gap", type=float, default=30)
    frames.add_argument("--pixel-threshold", type=float, default=20)
    frames.add_argument("--change-ratio", type=float, default=0.015)
    frames.add_argument("--tile-ratio", type=float, default=0.12)
    frames.add_argument("--crop", help="Comparison region in original pixels: x,y,width,height")
    frames.add_argument("--timestamps", help="Extract only these comma-separated times in seconds")

    transcribe = sub.add_parser("transcribe", help="Word-timed transcription")
    transcribe.add_argument("audio", type=Path)
    transcribe.add_argument("output", type=Path)
    transcribe.add_argument("--model", default="small")
    transcribe.add_argument("--language")
    transcribe.add_argument("--device", default="cpu")
    transcribe.add_argument("--compute-type", default="int8")

    diarize = sub.add_parser("diarize", help="Detect speaker turns")
    diarize.add_argument("audio", type=Path)
    diarize.add_argument("output", type=Path, help="Path to speaker_turns.json")
    diarize.add_argument("--model", default=DEFAULT_MODEL)
    diarize.add_argument("--min-speakers", type=_positive_int)
    diarize.add_argument("--max-speakers", type=_positive_int)

    label = sub.add_parser("label", help="Combine a raw transcript with speaker turns")
    label.add_argument("raw_transcript", type=Path)
    label.add_argument("speaker_turns", type=Path)
    label.add_argument("output", type=Path, help="Meeting directory for transcript.json/md")

    return parser


def _scan_settings(parser: argparse.ArgumentParser, args) -> tuple[ScanSettings, dict]:
    from meeting_digest.frames import ScanSettings, Thresholds

    for key in _SCAN_FLOATS:
        value = getattr(args, key)
        if not math.isfinite(value) or value <= 0:
            parser.error(f"--{key.replace('_', '-')} must be positive and finite.")
    if args.change_ratio > 1 or args.tile_ratio > 1 or args.pixel_threshold > 255:
        parser.error("Ratios must be <= 1; pixel threshold must be <= 255.")
    settings = ScanSettings(
        sample_fps=args.sample_fps,
        stable_seconds=args.stable_seconds,
        motion_interval=args.motion_interval,
        max_gap=args.max_gap,
        thresholds=Thresholds(
            pixel_threshold=args.pixel_threshold,
            change_ratio=args.change_ratio,
            tile_ratio=args.tile_ratio,
        ),
    )
    record = {key: getattr(args, key) for key in _SCAN_FLOATS}
    record.update(crop=args.crop, timestamps=args.timestamps)
    return settings, record


def _parse_crop(parser: argparse.ArgumentParser, raw: str | None):
    if not raw:
        return None
    try:
        crop = tuple(int(part) for part in raw.split(","))
    except ValueError:
        parser.error("--crop must contain four integers.")
    if len(crop) != 4:
        parser.error("--crop must contain four integers.")
    return crop


def _parse_timestamps(parser: argparse.ArgumentParser, raw: str | None):
    if not raw:
        return None
    try:
        times = sorted({float(part) for part in raw.split(",")})
    except ValueError:
        parser.error("Timestamps must be numbers separated by commas.")
    if any(not math.isfinite(t) for t in times):
        parser.error("Timestamps must be finite numbers.")
    return times


def _run_command(parser: argparse.ArgumentParser, args) -> int:
    if args.command == "check":
        print(json.dumps(dependencies(), indent=2))
        return 0

    from meeting_digest import pipeline
    from meeting_digest.audio import extract_audio

    require_dependencies()

    if args.command == "extract-audio":
        print(extract_audio(args.video, args.output))
    elif args.command == "frames":
        settings, record = _scan_settings(parser, args)
        print(
            pipeline.select_frames(
                args.video,
                args.output,
                settings,
                _parse_crop(parser, args.crop),
                _parse_timestamps(parser, args.timestamps),
                record,
            )
        )
    elif args.command == "transcribe":
        print(
            pipeline.write_transcript(
                args.audio,
                args.output,
                model=args.model,
                language=args.language,
                device=args.device,
                compute_type=args.compute_type,
            )
        )
    elif args.command == "diarize":
        if args.min_speakers and args.max_speakers and args.min_speakers > args.max_speakers:
            parser.error("--min-speakers cannot exceed --max-speakers.")
        print(
            pipeline.write_speaker_turns(
                args.audio,
                args.output,
                model=args.model,
                min_speakers=args.min_speakers,
                max_speakers=args.max_speakers,
            )
        )
    elif args.command == "label":
        print(
            pipeline.write_labeled_transcript(args.raw_transcript, args.speaker_turns, args.output)
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1
    try:
        return _run_command(parser, args)
    except DigestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
