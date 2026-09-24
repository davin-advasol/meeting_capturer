import pytest

from meeting_digest.errors import DigestError
from meeting_digest.labeling import label, speaker_for, validate_interval


def turn(start, end, speaker):
    return {"start": start, "end": end, "source_speaker": speaker}


def word(start, end, text=" hi"):
    return {"start": start, "end": end, "text": text}


def test_a_word_inside_one_turn_gets_that_speaker():
    assert speaker_for(word(1.0, 1.5), [turn(0.0, 3.0, "SPEAKER_00")]) == "SPEAKER_00"


def test_a_word_with_no_overlapping_turn_is_unattributed():
    assert speaker_for(word(5.0, 5.5), [turn(0.0, 3.0, "SPEAKER_00")]) is None


def test_a_word_split_evenly_between_two_speakers_is_unattributed():
    turns = [turn(0.0, 1.0, "SPEAKER_00"), turn(1.0, 2.0, "SPEAKER_01")]
    assert speaker_for(word(0.5, 1.5), turns) is None


def test_a_word_barely_touching_a_turn_is_unattributed():
    # 0.1s of a 1.0s word overlaps, which is under the 50% floor.
    assert speaker_for(word(0.0, 1.0), [turn(0.9, 3.0, "SPEAKER_00")]) is None


def test_a_clear_majority_wins_over_a_brief_second_speaker():
    turns = [turn(0.0, 0.95, "SPEAKER_00"), turn(0.95, 2.0, "SPEAKER_01")]
    assert speaker_for(word(0.0, 1.0), turns) == "SPEAKER_00"


def test_validate_interval_rejects_a_negative_start():
    with pytest.raises(DigestError, match="interval"):
        validate_interval({"start": -1.0, "end": 1.0})


def test_validate_interval_rejects_a_reversed_interval():
    with pytest.raises(DigestError, match="interval"):
        validate_interval({"start": 2.0, "end": 1.0})


def test_validate_interval_rejects_a_non_numeric_value():
    with pytest.raises(DigestError, match="interval"):
        validate_interval({"start": "0", "end": 1.0})


RAW = {
    "source": "/tmp/audio.wav",
    "language": "en",
    "backend": "faster-whisper/small",
    "segments": [
        {
            "start": 0.0,
            "end": 2.0,
            "text": "hello there",
            "words": [word(0.0, 0.5, " hello"), word(0.6, 1.0, " there")],
        },
        {
            "start": 3.0,
            "end": 4.0,
            "text": "goodbye",
            "words": [word(3.0, 3.5, " goodbye")],
        },
    ],
}
DIARIZATION = {
    "source": "/tmp/audio.wav",
    "backend": "pyannote/speaker-diarization-community-1",
    "turns": [turn(0.0, 2.0, "SPEAKER_07"), turn(2.5, 4.0, "SPEAKER_03")],
}


def test_label_numbers_speakers_by_first_occurrence():
    result = label(RAW, DIARIZATION)
    assert result["speakers"] == {"SPEAKER_07": "Speaker 1", "SPEAKER_03": "Speaker 2"}


def test_label_merges_adjacent_words_from_the_same_speaker():
    segments = label(RAW, DIARIZATION)["segments"]
    assert len(segments) == 2
    assert segments[0]["speaker"] == "Speaker 1"
    assert segments[0]["text"] == "hello there"
    assert segments[1]["speaker"] == "Speaker 2"


def test_label_requires_word_timestamps():
    raw = {**RAW, "segments": [{"start": 0.0, "end": 1.0, "text": "hi", "words": []}]}
    with pytest.raises(DigestError, match="Word timestamps"):
        label(raw, DIARIZATION)
