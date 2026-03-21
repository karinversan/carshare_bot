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
    require_real_inference: bool = True
    public_web_base_url: str = "http://localhost:5173"

    jwt_secret: str = "supersecret"
    auth_enabled: bool = False  # Set to True in production

    # Celery async dispatch: when True, damage inference is sent to a worker
    # instead of running synchronously in the API request.
    async_inference: bool = False
    celery_broker_url: str = "redis://localhost:6379/1"

    # Automatic damage decisioning thresholds for finalize/comparison flow.
    # >= high => auto-confirmed damage, [low, high) => uncertain/admin-review candidate.
    damage_auto_confirm_confidence: float = 0.7
    damage_auto_uncertain_confidence: float = 0.45

settings = Settings()
