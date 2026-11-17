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

    # 系统问答 · Phase B 检索版（零 LLM）
    faq_min_score: float = 0.60      # bge 余弦阈值：真命中≥0.68，无关问题≤0.43，取 0.60
    help_llm_enabled: bool = False   # Phase B Step 3：是否启用 LLM 生成（默认关）

    # AI 问答 · 外部 LLM（DeepSeek，OpenAI 兼容接口）
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-flash"
    llm_timeout: float = 10.0        # 单次生成最长等待（秒），超时退回原文
    llm_max_tokens: int = 300        # 回答很短即可，限制生成长度防长思考卡顿
    llm_reasoning_effort: str = "low"  # deepseek-flash 支持 low/high/max；low 减少长思考


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
