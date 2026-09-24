from meeting_digest.audio import build_filters


def test_aligned_audio_only_resets_the_timeline():
    assert build_filters(0.0) == ["asetpts=PTS-STARTPTS"]


def test_late_audio_is_padded_with_silence():
    assert build_filters(0.5) == ["asetpts=PTS-STARTPTS", "adelay=500:all=1"]


def test_padding_is_rounded_to_whole_milliseconds():
    assert build_filters(0.1234) == ["asetpts=PTS-STARTPTS", "adelay=123:all=1"]


def test_early_audio_is_trimmed_then_reset():
    assert build_filters(-0.25) == [
        "asetpts=PTS-STARTPTS",
        "atrim=start=0.25",
        "asetpts=PTS-STARTPTS",
    ]
