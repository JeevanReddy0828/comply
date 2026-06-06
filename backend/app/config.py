from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://comply:comply@localhost:5432/comply"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    catalog_dir: str = "../compliance"

    cors_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:5175"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def catalog_path(self) -> Path:
        return Path(self.catalog_dir).resolve()


settings = Settings()
