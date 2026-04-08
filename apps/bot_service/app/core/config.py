from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = "replace-me"
    api_base_url: str = "http://localhost:8000"
    api_service_url: str = "http://localhost:8000"  # alias for docker networking
    public_api_base_url: str = ""
    internal_service_token: str = "change-me-internal"
    miniapp_base_url: str = "http://localhost:5173"
    admin_panel_url: str = ""
    telegram_polling_enabled: bool = False
    telegram_polling_timeout_sec: int = 20

    @property
    def effective_api_url(self) -> str:
        """Use api_service_url if set to non-default, else api_base_url."""
        if self.api_service_url != "http://localhost:8000":
            return self.api_service_url
        return self.api_base_url

    @property
    def effective_admin_panel_url(self) -> str:
        if self.admin_panel_url:
            return self.admin_panel_url.rstrip("/") + "/"
        return f"{self.miniapp_base_url.rstrip('/')}/admin/"


settings = Settings()
