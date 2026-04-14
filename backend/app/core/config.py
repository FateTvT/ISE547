from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "local"
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        extra="ignore",
    )

    BACKEND_PORT: int = 8000
    BACKEND_HOST: str = "0.0.0.0"
    API_V1_STR: str = "/api/v1"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    DEFAULT_CHAT_MODEL: str = "qwen/qwen3-30b-a3b-instruct-2507"
    CHAT_TEMPERATURE: float = 0.2
    LANGGRAPH_SQLITE_DB_PATH: str = "langgraph.sqlite"
    SYSTEM_PROMPT: str = "You are a helpful assistant."


settings = Settings()
