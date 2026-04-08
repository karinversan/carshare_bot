from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    debug: bool = True

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/car_inspection"
    sync_database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/car_inspection"

    redis_url: str = "redis://localhost:6379/0"

    s3_endpoint_url: str = "http://localhost:9000"
    s3_external_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_region: str = "us-east-1"
    s3_secure: bool = False

    s3_bucket_raw_images: str = "raw-images"
    s3_bucket_processed_images: str = "processed-images"
    s3_bucket_overlays: str = "overlays"
    s3_bucket_closeups: str = "closeups"
    s3_bucket_reports: str = "reports"
    s3_bucket_ml_artifacts: str = "ml-artifacts"

    inference_service_url: str = "http://localhost:8010"
    bot_service_base_url: str = "http://localhost:8001"
    require_real_inference: bool = True
    public_web_base_url: str = "http://localhost:5173"
    public_api_base_url: str = ""

    jwt_secret: str = "supersecret"
    auth_enabled: bool = False  # Set to True in production
    internal_service_token: str = "change-me-internal"
    asset_url_secret: str = ""
    admin_demo_email: str = "admin@example.com"
    admin_demo_password: str = "admin123"
    cors_allowed_origins: str = ""

    # Celery async dispatch: when True, damage inference is sent to a worker
    # instead of running synchronously in the API request.
    async_inference: bool = False
    celery_broker_url: str = "redis://localhost:6379/1"

    # Automatic damage decisioning thresholds for finalize/comparison flow.
    # >= high => auto-confirmed damage, [low, high) => uncertain/admin-review candidate.
    damage_auto_confirm_confidence: float = 0.7
    damage_auto_uncertain_confidence: float = 0.45

    @property
    def effective_cors_allowed_origins(self) -> list[str]:
        if self.cors_allowed_origins.strip():
            return [
                origin.strip()
                for origin in self.cors_allowed_origins.split(",")
                if origin.strip()
            ]

        origins = {
            self.public_web_base_url.rstrip("/"),
            self.public_api_base_url.rstrip("/"),
        }
        for candidate in (self.public_web_base_url, self.public_api_base_url):
            parsed = urlparse(candidate)
            if parsed.scheme and parsed.netloc:
                origins.add(f"{parsed.scheme}://{parsed.netloc}")
        return [origin for origin in origins if origin]

settings = Settings()
