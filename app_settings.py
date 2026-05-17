"""
app_settings.py
Centralized application settings using Pydantic Settings.
Allows environment variable overrides and .env file support.
Related: app_config.py, ui/data_loader.py, batch/api_server.py
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    db_path: str = "data/toilets.db"
    db_backup_dir: str = "data/backups"

    # Scoring
    score_min: int = 0
    score_max: int = 100
    max_sample_reviews: int = 5
    review_text_max_length: int = 200

    # App
    default_language: str = "ja"
    sentry_dsn: str = ""
    sentry_environment: str = "development"

    # CORS (allowed origins for API)
    cors_origins: list[str] = ["*"]

    # API
    api_rate_limit: str = "10/minute"
    api_port: int = 8080

    # Map
    map_default_zoom: int = 10
    map_max_zoom: int = 18
    tile_openstreetmap: str = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
    tile_cartodb_dark: str = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"

    model_config = {"env_prefix": "TOILET_MAP_", "env_file": ".env"}


settings = Settings()
