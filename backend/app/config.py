from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="JEEVIA_", extra="ignore")

    env: str = "dev"
    # H3: how much runs on this machine. stub = rules only (no speech, translation, OCR, summary model or online engines:
    # CI and the free cloud demo); demo = everything loads on first use (laptop default); full = models load at
    # start-up and the summary model is expected. A setting given explicitly always wins over the profile.
    profile: Literal["stub", "demo", "full"] = "demo"
    language_models: bool = True  # offline speech recognition and translation
    ocr_enabled: bool = True
    # G8: where this deployment's records come from. Only SYNTHETIC or PUBLIC_SAMPLE; real patient data is out of scope.
    data_origin: Literal["SYNTHETIC", "PUBLIC_SAMPLE"] = "SYNTHETIC"
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
    demo_phones: str = "9000000001,9000000002,9000000003,9000000004,9000000005,9000000006,9000000007,9000000008,9000000009,9000000010"
    twilio_account_sid: str | None = None
    twilio_api_key_sid: str | None = None
    twilio_api_key_secret: str | None = None
    twilio_verify_service_sid: str | None = None
    sms_country_code: str = "+91"
    # Reminder calls over a real phone line and reminder SMS (app/telephony.py). The auth token checks that webhooks
    # really come from Twilio; the from-number is a Twilio number with voice and SMS.
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None  # E.164, e.g. +1415…
    # Vonage, the other provider (its free trial calls and texts the number the account was registered with). Used
    # instead of Twilio when its application is set. The private key file belongs to the Vonage application.
    vonage_api_key: str | None = None
    vonage_api_secret: str | None = None
    vonage_application_id: str | None = None
    vonage_private_key_path: str | None = None  # relative to backend/
    vonage_from_number: str = "123456789"  # Vonage's caller ID for trial accounts; a rented number once upgraded
    vonage_sms_from: str = "Jeevia"
    # Where Twilio or Vonage can reach this server (a tunnel in development): https://….trycloudflare.com
    public_base_url: str | None = None
    # Every call and SMS goes to this one number (E.164) and never to a patient's stored number: demo patients are
    # synthetic and their numbers may belong to real people. Unset = no calls or SMS are placed at all.
    telephony_demo_to: str | None = None
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
    # B9 offline second speech engine (app/whisper_asr.py): hears the recording when Sarvam (online) cannot.
    asr_second_offline: bool = True
    asr_second_int8: bool = True  # 8-bit IndicWhisper made at load time — see docs/EVALUATION.md
    # Note summary model (B5): llama.cpp llama-server, OpenAI-compatible. Unset = template summary only.
    llm_url: str | None = None
    llm_model_name: str = "Qwen3-4B-Instruct-2507 Q4_K_M (llama.cpp, offline)"
    llm_timeout_s: float = 30
    llm_urgency_opinion: bool = True  # C8: the model's own urgency tier, shown beside the rules' result (never replaces it)
    preload_language_models: bool = False  # load at start-up instead of on the first request
    # Sarvam AI (online, India-hosted): Bulbul voice for reminder-call lines, Saaras speech-to-text as a second engine.
    # Unset = calls fall back to the device's own voice. JEEVIA_SARVAM_API_KEY or SARVAM_API_KEY.
    sarvam_api_key: str | None = Field(None, validation_alias=AliasChoices("JEEVIA_SARVAM_API_KEY", "SARVAM_API_KEY"))
    sarvam_tts_speaker: str = "priya"  # a woman's voice: the Hindi lines speak as a woman ("समझ नहीं पाई")
    sarvam_timeout_s: float = 20

    escalate_red_min: int = 15
    escalate_yellow_min: int = 60
    # GREEN has no escalation: past this wait the medical officer is told, who decides (see them, refer, or a priority
    # token for the next day). The queue order itself never changes for it.
    green_long_wait_min: int = 120
    # An intake sent from home that nobody checked in leaves the expected list after this long.
    home_intake_valid_h: int = 36

    # Kiosk submissions by staff must come from a device bound to their facility.
    require_bound_device: bool = True

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    cors_origin_regex: str | None = r"https://jeevia[a-z0-9-]*\.vercel\.app"
    # Public base URL of the web app, used to build kiosk links.
    web_base_url: str = "http://localhost:3000"
    timezone: str = "Asia/Kolkata"
    seed_demo: bool = True
    seed_scenarios: bool = True  # demo scenarios for campus fevers, missed visits, capacity, workplace screening (app/scenarios.py)
    log_level: str = "INFO"


    @model_validator(mode="after")
    def _profile(self):
        given = self.model_fields_set
        preset = {"stub": {"language_models": False, "ocr_enabled": False, "asr_second_offline": False, "llm_url": None,
                           "llm_urgency_opinion": False, "preload_language_models": False, "sarvam_api_key": None},
                  "demo": {},
                  "full": {"preload_language_models": True}}[self.profile]
        for k, v in preset.items():
            if k not in given:
                object.__setattr__(self, k, v)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
