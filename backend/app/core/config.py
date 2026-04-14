from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ENVIRONMENT: str = "local"
    model_config = SettingsConfigDict(env_file="../.env",extra="ignore")
    BACKEND_PORT: int = 8000
    BACKEND_HOST: str = "0.0.0.0"
    API_V1_STR: str = "/api/v1"
settings = Settings()

