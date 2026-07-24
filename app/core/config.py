from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Mebel Catalog API"
    environment: str = "dev"
    database_url: str = "postgresql+asyncpg://catalog:catalog_password@localhost:5432/mebel_catalog"
    cors_origins: str = "http://localhost:3000"
    public_site_url: str = "http://localhost:3000"
    telegram_bot_token: str = ""
    super_admin_token: str = ""
    upload_dir: str = "uploads"
    max_upload_mb: int = 8
    # Bitta IP uchun daqiqasiga ruxsat etilgan buyurtmalar soni (in-process anti-spam).
    order_rate_limit_per_minute: int = 5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
