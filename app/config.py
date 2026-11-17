from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "ollama"  # "ollama" | "gemini"; the other is used as fallback if configured
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    max_content_chars: int = 9000  # ~2.5k tokens sent to the LLM
    fetch_timeout: float = 10.0
    max_response_bytes: int = 2_000_000
    llm_timeout: float = 180.0
    cache_ttl: int = 3600


settings = Settings()
