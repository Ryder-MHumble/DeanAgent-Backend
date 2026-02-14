from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/postgres"
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""

    # RSSHub
    RSSHUB_BASE_URL: str = "https://rsshub.app"

    # Playwright
    PLAYWRIGHT_MAX_CONTEXTS: int = 3

    # Scheduler
    MAX_CONCURRENT_CRAWLS: int = 5
    DEFAULT_REQUEST_DELAY: float = 1.0

    # Social media cookies
    WEIBO_COOKIE: str = ""
    XIAOHONGSHU_COOKIE: str = ""

    # API auth
    API_KEY: str = ""

    # OpenRouter LLM
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "google/gemini-2.0-flash-001"

    # Twitter API (twitterapi.io)
    TWITTER_API_KEY: str = ""
    TWITTER_API_PROXY: str = ""  # e.g. http://127.0.0.1:7890

    # Paths
    SOURCES_DIR: Path = BASE_DIR / "sources"


settings = Settings()
