"""探活不依赖业务路由；就绪检查只访问已启用组件并隐藏连接详情。"""

import asyncio

from fastapi import APIRouter, Request, Response

from app.schemas.common import ApiResponse
from app.schemas.health import (
    DependencyStatus,
    HealthResponse,
    ReadinessChecks,
    ReadinessResponse,
)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=ApiResponse[HealthResponse])
async def health() -> ApiResponse[HealthResponse]:
    """HTTP 服务存活即可成功，外部组件异常不会改变存活判断。"""
    return ApiResponse(data=HealthResponse())


async def database_status(request: Request) -> DependencyStatus:
    engine = request.app.state.db_engine
    if engine is None:
        return "error" if request.app.state.settings.database_url else "disabled"

    from app.db.session import check_database

    try:
        async with asyncio.timeout(request.app.state.settings.dependency_timeout_seconds):
            await check_database(engine)
    except Exception:
        return "error"
    return "ok"


async def redis_status(request: Request) -> DependencyStatus:
    client = request.app.state.redis_client
    if client is None:
        return "error" if request.app.state.settings.redis_url else "disabled"
    try:
        async with asyncio.timeout(request.app.state.settings.dependency_timeout_seconds):
            if not await client.ping():
                return "error"
    except Exception:
        return "error"
    return "ok"


@router.get(
    "/ready",
    response_model=ApiResponse[ReadinessResponse],
    responses={503: {"model": ApiResponse[ReadinessResponse]}},
)
async def ready(request: Request, response: Response) -> ApiResponse[ReadinessResponse]:
    """启动后重新检查组件，任一失败则返回真实 HTTP 503 和统一错误响应。"""
    database, redis = await asyncio.gather(database_status(request), redis_status(request))
    available = database != "error" and redis != "error"
    response.status_code = 200 if available else 503
    data = ReadinessResponse(
        status="ok" if available else "error",
        checks=ReadinessChecks(database=database, redis=redis),
    )
    return ApiResponse(
        status_code=response.status_code,
        status="success" if available else "error",
        data=data,
        messages="" if available else "Configured dependency is unavailable",
    )
