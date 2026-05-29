from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "dev"

    database_url: str | None = None

    tmdb_api_key: str | None = None
    spotify_client_id: str | None = None
    spotify_client_secret: str | None = None

    gemini_api_key: str | None = None
    groq_api_key: str | None = None

    google_client_id: str | None = None

    daily_query_cap: int = 500

    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
