from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/word_planet"
    jwt_secret: str = "change-me-in-env"
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7

    app_timezone: str = "Asia/Shanghai"
    enable_scheduler: bool = False

    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:admin@example.com"

    # 讯飞语音评测 / 实时转写（未填 key 时自动走 mock，不影响功能演示）
    iflytek_app_id: str = ""
    iflytek_api_key: str = ""
    iflytek_api_secret: str = ""
    iflytek_enabled: bool = False


    cors_origins: str = "http://localhost:5273,https://localhost:5273"

    # 公网安全开关（本机开发默认关闭；生产 .env 打开）
    require_captcha: bool = False
    rate_limit_per_min: int = 0  # 0 = 关闭

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
