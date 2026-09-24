"""Local screenshot candidate selection. No vision model is involved.

The comparison runs on small grayscale samples; selected timestamps are later
re-extracted at full resolution from the source file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from meeting_digest.errors import DigestError
from meeting_digest.ffmpeg import stream_gray_frames

SAMPLE_WIDTH = 640
TILE_GRID = 8


@dataclass(frozen=True)
class Thresholds:
    """How much a sample must differ before it counts as a change."""

    pixel_threshold: float = 20.0
    change_ratio: float = 0.015
    tile_ratio: float = 0.12


@dataclass(frozen=True)
class ScanSettings:
    """Sampling cadence and the rules that turn changes into candidates."""

    sample_fps: float = 2.0
    stable_seconds: float = 1.0
    motion_interval: float = 5.0
    max_gap: float = 30.0
    thresholds: Thresholds = field(default_factory=Thresholds)


def changed(a, b, thresholds: Thresholds) -> bool:
    """Whether two samples differ enough to matter.

    Compares both the overall changed area and the worst 8x8 tile, so a small
    localized edit — a line added to a slide — is not averaged away.
    """
    mask = cv2.absdiff(a, b) > thresholds.pixel_threshold
    overall = float(mask.mean())
    tiles = [
        float(tile.mean())
        for row in np.array_split(mask, TILE_GRID, axis=0)
        for tile in np.array_split(row, TILE_GRID, axis=1)
    ]
    return overall >= thresholds.change_ratio or max(tiles) >= thresholds.tile_ratio


class Selector:
    """Decides which sampled frames become screenshot candidates."""

    def __init__(self, settings: ScanSettings):
        self.settings = settings
        self.previous = self.selected = None
        self.selected_at = 0.0
        self.last_motion = 0.0
        self.onset = None

    def consider(self, t: float, frame) -> dict | None:
        settings = self.settings
        reason = None
        if self.previous is None:
            reason = "initial"
        else:
            moving = changed(frame, self.previous, settings.thresholds)
            different = changed(frame, self.selected, settings.thresholds)
            if moving:
                self.last_motion = t
            if different and self.onset is None:
                self.onset = t
            if not different:
                self.onset = None
            if different and t - self.last_motion >= settings.stable_seconds:
                reason = "settled_change"
            elif different and t - self.selected_at >= settings.motion_interval:
                reason = "motion_fallback"
            elif t - self.selected_at >= settings.max_gap:
                reason = "coverage"
        self.previous = frame.copy()
        if reason:
            result = {
                "timestamp": round(t, 6),
                "reason": reason,
                "approximate_change_start": self.onset,
            }
            self.selected, self.selected_at = frame.copy(), t
            self.onset = None
            return result
        return None


def build_scan_filters(
    stream: dict, crop: tuple[int, int, int, int] | None, sample_fps: float
) -> tuple[list[str], int, int]:
    """Build the sampling filter chain and the resulting sample dimensions."""
    width, height = stream["width"], stream["height"]
    filters = ["setpts=PTS-STARTPTS"]
    if crop:
        x, y, width, height = crop
        if (
            x < 0
            or y < 0
            or width < 8
            or height < 8
            or x + width > stream["width"]
            or y + height > stream["height"]
        ):
            raise DigestError("Crop is outside the video dimensions or too small.")
        filters.append(f"crop={width}:{height}:{x}:{y}")
    out_width = min(SAMPLE_WIDTH, width)
    out_height = max(8, round(height * out_width / width))
    filters.extend(
        [
            f"fps={sample_fps}:round=up",
            f"scale={out_width}:{out_height}",
            "format=gray",
        ]
    )
    return filters, out_width, out_height


def scan(
    video: Path,
    stream: dict,
    offset: float,
    settings: ScanSettings,
    crop: tuple[int, int, int, int] | None = None,
) -> tuple[list[dict], int]:
    """Sample the video locally and return candidate timestamps plus sample count."""
    filters, width, height = build_scan_filters(stream, crop, settings.sample_fps)
    selector = Selector(settings)
    selections: list[dict] = []
    index = 0
    last = None
    for frame in stream_gray_frames(video, stream["index"], filters, width, height):
        frame = cv2.GaussianBlur(frame, (3, 3), 0)
        t = offset + index / settings.sample_fps
        last = (t, frame)
        choice = selector.consider(t, frame)
        if choice:
            selections.append(choice)
        index += 1
    if (
        last
        and selector.selected is not None
        and changed(last[1], selector.selected, settings.thresholds)
    ):
        selections.append(
            {
                "timestamp": round(last[0], 6),
                "reason": "final_change",
                "approximate_change_start": selector.onset,
            }
        )
    return selections, index
