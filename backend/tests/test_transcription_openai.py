from app.transcription.openai_adapter import _parse_diarized_response


def test_parse_diarized_response_builds_segments():
    data = {
        "segments": [
            {"speaker": "Speaker 1", "start": 0.0, "end": 4.2, "text": "Hi"},
            {"speaker": "Speaker 2", "start": 4.5, "end": 9.8, "text": "Hello"},
        ]
    }
    segments = _parse_diarized_response(data)
    assert [s.id for s in segments] == [0, 1]
    assert segments[1].speaker == "Speaker 2"
    assert segments[0].text == "Hi"
