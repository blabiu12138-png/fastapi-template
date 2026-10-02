"""配置仅读取当前模板根目录的 .env，不依赖进程工作目录。"""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """应用配置入口：环境变量优先于项目根目录 .env。

    新增配置时在此声明字段，并同步更新 .env.example。数据库 URL 使用
    SQLAlchemy 的 dialect+driver 格式，实际解析留到组件启用时执行，
    使基础安装无需导入 SQLAlchemy。测试可用 Settings(_env_file=None) 禁用 dotenv。
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        hide_input_in_errors=True,
        extra="ignore",
    )

    app_name: str = "FastAPI Application"
    environment: str = "development"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["console", "json"] = "console"
    cors_origins: list[str] = Field(default_factory=list)
    # 空 URL 关闭组件；repr=False 避免打印 Settings 时暴露连接凭据。
    database_url: str | None = Field(default=None, repr=False)
    redis_url: str | None = Field(default=None, repr=False)
    dependency_timeout_seconds: float = Field(default=5.0, gt=0)

    @field_validator("database_url", "redis_url", mode="before")
    @classmethod
    def empty_url_disables_component(cls, value: str | None) -> str | None:
        return None if value == "" else value

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL must use redis:// or rediss://")
        return value
