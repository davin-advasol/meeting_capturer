from meeting_digest.transcribe import render_markdown, segments_from_model


class FakeWord:
    def __init__(self, start, end, text):
        self.start, self.end, self.word = start, end, text


class FakeSegment:
    def __init__(self, start, end, text, words):
        self.start, self.end, self.text, self.words = start, end, text, words


def test_segments_from_model_keeps_word_timings():
    raw = [FakeSegment(0.0, 1.0, " hello ", [FakeWord(0.0, 0.5, " hello")])]
    rows = segments_from_model(raw)
    assert rows == [
        {
            "start": 0.0,
            "end": 1.0,
            "text": "hello",
            "words": [{"start": 0.0, "end": 0.5, "text": " hello"}],
        }
    ]


def test_segments_from_model_drops_words_without_timings():
    raw = [FakeSegment(0.0, 1.0, "hi", [FakeWord(None, 0.5, " hi"), FakeWord(0.6, 1.0, " you")])]
    assert len(segments_from_model(raw)[0]["words"]) == 1


def test_segments_from_model_tolerates_a_segment_with_no_words():
    raw = [FakeSegment(0.0, 1.0, "hi", None)]
    assert segments_from_model(raw)[0]["words"] == []


def test_render_markdown_uses_readable_timestamps():
    rows = [{"start": 0.0, "end": 1.5, "text": "hello"}]
    assert render_markdown(rows) == "# Transcript\n\n[00:00:00.000–00:00:01.500] hello"
