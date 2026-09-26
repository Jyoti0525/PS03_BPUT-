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

    # OTP: "mock" returns the code in the API response (local dev only); "twilio" uses Twilio Verify.
    otp_provider: str = "mock"
    demo_otp: str | None = "123456"
    # Sample accounts that may use demo_otp even when a real SMS provider is configured.
    demo_phones: str = "9000000001,9000000002,9000000003,9000000004,9000000005,9876543210"
    twilio_account_sid: str | None = None
    twilio_api_key_sid: str | None = None
    twilio_api_key_secret: str | None = None
    twilio_verify_service_sid: str | None = None
    sms_country_code: str = "+91"
    otp_ttl_sec: int = 300
    otp_max_attempts: int = 5

    # Object storage: "local" disk, or "s3" for any S3-compatible store (Cloudflare R2).
    storage_backend: str = "local"
    storage_dir: str = "./data/uploads"
    s3_endpoint: str | None = None  # https://<account_id>.r2.cloudflarestorage.com
    s3_bucket: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_region: str = "auto"
    max_upload_mb: int = 8
    retention_hours_audio: int = 24
    retention_hours_image: int = 72
    retention_hours_report: int = 168

    escalate_red_min: int = 15
    escalate_yellow_min: int = 60

    # Kiosk submissions by staff must come from a device bound to their facility.
    require_bound_device: bool = True

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    cors_origin_regex: str | None = r"https://jeevia[a-z0-9-]*\.vercel\.app"
    # Public base URL of the web app, used to build kiosk links.
    web_base_url: str = "http://localhost:3000"
    timezone: str = "Asia/Kolkata"
    seed_demo: bool = True
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
