from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="JEEVIA_", extra="ignore")

    env: str = "dev"
    database_url: str = "sqlite:///./data/jeevia.db"
    jwt_secret: str = "change-me-in-production-please-32b+"
    jwt_alg: str = "HS256"
    access_ttl_min: int = 60
    refresh_ttl_days: int = 7
    registration_ttl_min: int = 15
    file_url_ttl_min: int = 10

    # OTP: "mock" returns the code in the API response (demo only); anything else must send SMS.
    otp_provider: str = "mock"
    demo_otp: str | None = "123456"
    otp_ttl_sec: int = 300
    otp_max_attempts: int = 5

    storage_dir: str = "./data/uploads"
    max_upload_mb: int = 8
    retention_hours_audio: int = 24
    retention_hours_image: int = 72
    retention_hours_report: int = 168

    escalate_red_min: int = 15
    escalate_yellow_min: int = 60

    # Kiosk submissions by staff must come from a device bound to their facility.
    require_bound_device: bool = True

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    cors_origin_regex: str | None = r"https://.*\.vercel\.app"
    seed_demo: bool = True
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
