import pytest

from app.config import Settings
from app.llm.factory import get_chat_model


def test_unknown_provider_raises():
    settings = Settings(llm_provider="bogus")
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_chat_model(settings)


def test_anthropic_missing_key_raises():
    settings = Settings(llm_provider="anthropic", anthropic_api_key=None)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        get_chat_model(settings)


def test_openai_missing_key_raises():
    settings = Settings(llm_provider="openai", openai_api_key=None)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        get_chat_model(settings)
