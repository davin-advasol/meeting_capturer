import pytest

from meeting_digest.cli import build_parser, main


def parse(argv):
    return build_parser().parse_args(argv)


def test_check_needs_no_arguments():
    assert parse(["check"]).command == "check"


def test_frames_defaults_match_the_original_script():
    args = parse(["frames", "a.mp4", "out"])
    assert args.sample_fps == 2
    assert args.stable_seconds == 1
    assert args.motion_interval == 5
    assert args.max_gap == 30
    assert args.pixel_threshold == 20
    assert args.change_ratio == pytest.approx(0.015)
    assert args.tile_ratio == pytest.approx(0.12)


def test_transcribe_defaults_match_the_original_script():
    args = parse(["transcribe", "a.wav", "out"])
    assert args.model == "small"
    assert args.language is None
    assert args.device == "cpu"
    assert args.compute_type == "int8"


def test_an_unknown_command_exits_two():
    with pytest.raises(SystemExit) as exc:
        parse(["nonsense"])
    assert exc.value.code == 2


def test_a_digest_error_is_printed_without_a_traceback(capsys):
    code = main(["extract-audio", "definitely-missing.mp4", "out/audio.wav"])
    assert code == 2
    assert capsys.readouterr().err.startswith("error: ")


def test_check_reports_every_dependency(capsys):
    assert main(["check"]) == 0
    out = capsys.readouterr().out
    for name in ("ffmpeg", "ffprobe", "numpy", "cv2"):
        assert name in out


def test_frames_rejects_a_non_positive_threshold(capsys):
    with pytest.raises(SystemExit):
        main(["frames", "a.mp4", "out", "--sample-fps", "0"])


def test_frames_rejects_a_ratio_above_one():
    with pytest.raises(SystemExit):
        main(["frames", "a.mp4", "out", "--change-ratio", "2"])


def test_frames_rejects_a_malformed_crop():
    with pytest.raises(SystemExit):
        main(["frames", "a.mp4", "out", "--crop", "1,2,3"])
