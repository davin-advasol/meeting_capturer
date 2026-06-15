from app.config import Settings 

def test_allowed_ext_set_parses_and_normalizes(): 
    s = Settings(allowed_extensions=".MP4, .wav ,.mp3")
    assert s.allowed_ext_set() == {".mp4", ".wav", ".mp3"}

def test_default_presents(): 
    s = Settings()
    assert s.transcriber_model == "gpt-4o-transcribe-diarize"
    assert s.llm_provider == "anthropic"