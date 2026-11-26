from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from urllib.parse import urlparse


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "VISUAL EYES 360"
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "dev-only-secret-change-before-production"
    DATABASE_URL: str = "sqlite:///./visual_eyes_360_v2.db"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    SETUP_TOKEN: str = "change-this-setup-token"
    ALGORITHM: str = "HS256"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    PUBLIC_APP_URL: str = "http://127.0.0.1:5173"

    # ---- Alerting / email -------------------------------------------------
    # SMTP is configured only through environment variables. Nothing is
    # hardcoded: when SMTP_HOST is empty notifications stay queued (PENDING)
    # instead of pretending an email was delivered.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "VISUAL EYES 360"
    SMTP_USE_TLS: bool = True
    ALERT_EMAIL_RECIPIENTS: str = "olatmatics.tech@gmail.com"
    # Only genuinely critical operational events are emailed.
    ALERT_EMAIL_MIN_SEVERITY: str = "CRITICAL"

    # ---- Hardware ingestion ----------------------------------------------
    INGEST_API_KEY: str = "dev-ingest-key-change-me"
    INGEST_ALLOWED_CLOCK_SKEW_SECONDS: int = 900
    DUPLICATE_WINDOW_MINUTES: int = 1440

    # ---- Operational thresholds ------------------------------------------
    PUMP_DISCREPANCY_THRESHOLD_L: float = 0.49
    TANK_VARIANCE_WARNING_PCT: float = 0.5
    TANK_VARIANCE_CRITICAL_PCT: float = 1.5
    TANK_WATER_WARNING_MM: float = 25.0
    TANK_WATER_CRITICAL_MM: float = 50.0

    # ---- Scale-out: cache, device transport -------------------------------
    REDIS_URL: str = "redis://localhost:6379/0"
    MQTT_HOST: str = "localhost"
    MQTT_PORT: int = 1883
    MQTT_USERNAME: str = ""
    MQTT_PASSWORD: str = ""
    MQTT_TLS: bool = False
    MQTT_TOPIC_PREFIX: str = "ve360"
    TELEMETRY_RETENTION_MONTHS: int = 12
    DEVICE_OFFLINE_AFTER_MINUTES: int = 4   # 240 s bench ticker/window

    # ---- OPay POS gateway (prototype integration) ------------------------
    # Secrets are supplied through the environment / .env, never in code.
    OPAY_ENV: str = "staging"
    OPAY_BASE_URL: str = "https://testapi.opaycheckout.com"
    OPAY_MERCHANT_ID: str = ""
    OPAY_PRIVATE_KEY: str = ""
    OPAY_PUBLIC_KEY: str = ""
    OPAY_WEBHOOK_URL: str = "http://127.0.0.1:8000/api/v1/opay/webhook"
    USE_MOCK_OPAY_GATEWAY: bool = True
    MOCK_OPAY_URL: str = "http://127.0.0.1:8000/mock-opay"

    @model_validator(mode="after")
    def require_production_secrets(self):
        if self.ENVIRONMENT.lower() in {"production", "prod", "live"}:
            for name, value in (
                ("SECRET_KEY", self.SECRET_KEY),
                ("SETUP_TOKEN", self.SETUP_TOKEN),
                ("INGEST_API_KEY", self.INGEST_API_KEY),
            ):
                if (
                    len(value) < 32
                    or len(set(value)) < 8
                    or value.startswith("replace-")
                    or value in {
                        "dev-only-secret-change-before-production",
                        "change-this-setup-token",
                        "dev-ingest-key-change-me",
                    }
                ):
                    raise ValueError(f"Production requires a unique {name} of at least 32 characters")
            if self.DATABASE_URL.startswith("sqlite"):
                raise ValueError("Production requires PostgreSQL; SQLite is only supported for development and tests")
            if not self.cors_origin_list or any(origin == "*" for origin in self.cors_origin_list):
                raise ValueError("Production requires explicit CORS_ORIGINS; wildcard origins are not allowed")
            public_url = urlparse(self.PUBLIC_APP_URL)
            if public_url.scheme != "https" or not public_url.netloc:
                raise ValueError("Production PUBLIC_APP_URL must be an HTTPS URL")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def alert_recipient_list(self) -> list[str]:
        return [r.strip() for r in self.ALERT_EMAIL_RECIPIENTS.split(",") if r.strip()]

    @property
    def smtp_configured(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_FROM_EMAIL)


settings = Settings()
