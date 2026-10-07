import numpy as np
import pytest

from meeting_digest.errors import DigestError
from meeting_digest.frames import (
    ScanSettings,
    Selector,
    Thresholds,
    build_scan_filters,
    changed,
)

SIZE = (64, 64)


def blank(value=0):
    return np.full(SIZE, value, dtype=np.uint8)


def test_identical_frames_are_unchanged():
    assert changed(blank(), blank(), Thresholds()) is False


def test_a_small_bright_block_trips_the_tile_ratio():
    # A 6x6 block sits inside a single 8x8 tile, giving that tile a mean of
    # 0.5625 (far past tile_ratio=0.12), while changing only 0.88% of the frame
    # overall — under change_ratio=0.015. So ONLY the tile check can trip this.
    a, b = blank(), blank()
    b[0:6, 0:6] = 255
    assert changed(a, b, Thresholds()) is True


def test_diffuse_noise_below_the_pixel_threshold_is_ignored():
    a, b = blank(100), blank(110)  # 10 < pixel_threshold of 20
    assert changed(a, b, Thresholds()) is False


def test_a_full_frame_change_is_detected():
    assert changed(blank(0), blank(255), Thresholds()) is True


def test_the_first_frame_is_always_selected():
    selector = Selector(ScanSettings())
    result = selector.consider(0.0, blank())
    assert result["reason"] == "initial"
    assert result["timestamp"] == 0.0


def test_a_settled_change_is_selected_after_the_stability_window():
    settings = ScanSettings(sample_fps=2.0, stable_seconds=1.0)
    selector = Selector(settings)
    selector.consider(0.0, blank(0))
    # Change appears; motion is still happening, so it is not selected yet.
    assert selector.consider(0.5, blank(255)) is None
    # Screen is now static; after stable_seconds have passed it settles.
    assert selector.consider(1.0, blank(255)) is None
    result = selector.consider(1.5, blank(255))
    assert result["reason"] == "settled_change"


def test_coverage_fires_when_nothing_changes_for_max_gap():
    settings = ScanSettings(max_gap=2.0)
    selector = Selector(settings)
    selector.consider(0.0, blank())
    assert selector.consider(1.0, blank()) is None
    assert selector.consider(2.0, blank())["reason"] == "coverage"


def test_build_scan_filters_downscales_to_640_wide():
    stream = {"width": 1920, "height": 1080}
    filters, width, height = build_scan_filters(stream, None, 2.0)
    assert (width, height) == (640, 360)
    assert "fps=2.0:round=up" in filters
    assert "scale=640:360" in filters
    assert filters[-1] == "format=gray"


def test_build_scan_filters_applies_a_crop():
    stream = {"width": 1920, "height": 1080}
    filters, width, height = build_scan_filters(stream, (100, 50, 800, 600), 2.0)
    assert "crop=800:600:100:50" in filters
    assert (width, height) == (640, 480)


def test_build_scan_filters_rejects_a_crop_outside_the_frame():
    with pytest.raises(DigestError, match="outside the video"):
        build_scan_filters({"width": 640, "height": 480}, (600, 0, 100, 100), 2.0)


def test_build_scan_filters_rejects_a_tiny_crop():
    with pytest.raises(DigestError, match="outside the video|too small"):
        build_scan_filters({"width": 640, "height": 480}, (0, 0, 4, 4), 2.0)
