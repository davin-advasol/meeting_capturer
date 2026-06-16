import pytest

from app.config import Settings
from app.transcription.factory import get_transcriber


def test_get_transcriber_openai():
    settings = Settings(transcriber_provider="openai", openai_api_key="sk-test")
    t = get_transcriber(settings)
    assert t.name.startswith("openai:")


def test_get_transcriber_missing_key_raises():
    settings = Settings(transcriber_provider="openai", openai_api_key=None)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        get_transcriber(settings)


def test_get_transcriber_unknown_provider_raises():
    settings = Settings(transcriber_provider="bogus")
    with pytest.raises(ValueError, match="Unknown transcriber provider"):
        get_transcriber(settings)
