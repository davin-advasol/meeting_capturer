from functools import lru_cache 

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    data_dir: str = "./data"
    transcriber_provider: str = "openai"
    transcriber_model: str = "gpt-4o-transcribe-diarize"
    openai_api_key: str | None = None
    llm_provider: str = "anthropic"
    llm_model: str = "claude-opus-4-8"
    anthropic_api_key: str | None = None
    allowed_extensions: str = ".mp4,.mkv,.mov,.webm,.mp3,.m4a,.wav"
    vad_min_silence_sec: float = 1.5

    def allowed_ext_set(self) -> set[str]:
        return {e.strip().lower() for e in self.allowed_extensions.split(",") if e.strip()}
    
@lru_cache()
def get_settings() -> Settings:
    return Settings()