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
    # Optional email codes: "none" (off), "mock" (local dev), "brevo" (Brevo transactional email API).
    email_provider: str = "none"
    brevo_api_key: str | None = None
    email_from: str | None = None
    email_from_name: str = "Jeevia"
    otp_ttl_sec: int = 300
    otp_max_attempts: int = 5
    otp_per_phone_10min: int = 3
    otp_per_phone_day: int = 10
    otp_per_ip_hour: int = 30
    # PIN (second factor) for sample walkthrough accounts only.
    demo_pin: str = "4826"
    pin_max_attempts: int = 5
    pin_lock_minutes: int = 15
    pin_step_ttl_min: int = 5

    # Object storage: "local" disk, or "s3" for any S3-compatible store (Cloudflare R2).
    storage_backend: str = "local"
    storage_dir: str = "./data/uploads"
    s3_endpoint: str | None = None  # https://<account_id>.r2.cloudflarestorage.com
    s3_bucket: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_region: str = "auto"
    cloudinary_cloud_name: str | None = None
    cloudinary_api_key: str | None = None
    cloudinary_api_secret: str | None = None
    max_upload_mb: int = 8
    retention_hours_audio: int = 24
    retention_hours_image: int = 72
    retention_hours_report: int = 720  # 30 days, so reports travel with referrals
    directory_autoload: bool = True  # load directory_data/ snapshot into an empty facility_directory at start-up

    # Offline speech / translation models (see app/language.py). Relative paths are from backend/.
    models_dir: str = "../models"
    # 8-bit copy made by scripts/quantize_asr.py: same accuracy, ~half the RAM (docs/EVALUATION.md).
    # "indic-conformer-600m-multilingual" = the original fp32 download.
    asr_model: str = "indic-conformer-600m-int8"
    asr_decoding: str = "ctc"  # "ctc" (2x faster) or "rnnt" (slightly more accurate) — see docs/EVALUATION.md
    # Note summary model (B5): llama.cpp llama-server, OpenAI-compatible. Unset = template summary only.
    llm_url: str | None = None
    llm_model_name: str = "Qwen3-4B-Instruct-2507 Q4_K_M (llama.cpp, offline)"
    llm_timeout_s: float = 30
    preload_language_models: bool = False  # load at start-up instead of on the first request

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
