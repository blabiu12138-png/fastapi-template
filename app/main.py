"""应用工厂；启动命令：uv run uvicorn app.main:app --reload。"""

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import Settings
from app.core.exception_handlers import setup_exception_handlers
from app.core.lifespan import lifespan
from app.core.logging import setup_logging
from app.middleware.request_context import RequestContextMiddleware
from app.schemas.common import ApiResponse


def create_app(settings: Settings | None = None) -> FastAPI:
    """组合基础设施与路由；测试或多实例场景可以传入独立 Settings。

    新接口在 app.api.router 注册；新组件在 lifespan 初始化，再通过依赖读取 state。
    入口只负责组装，不创建表、不执行迁移、不实现业务逻辑。
    """
    settings = settings if settings is not None else Settings()
    setup_logging(settings)
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
        responses={
            status_code: {"model": ApiResponse[dict[str, Any]]}
            for status_code in (400, 404, 409, 422, 500, 503)
        },
    )
    # state 归属当前 app，避免多个应用实例共享连接或配置。
    app.state.settings = settings
    app.state.db_engine = None
    app.state.db_session_factory = None
    app.state.redis_client = None

    app.include_router(api_router)
    setup_exception_handlers(app)
    app.add_middleware(RequestContextMiddleware)
    # 放在请求上下文之外，让正常响应与 500 响应都经过 CORS。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    return app


app = create_app()
