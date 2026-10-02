"""按配置创建外部资源，启动失败和关闭时均按逆序释放。"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """在接受请求前初始化配置过的组件，退出时释放共享资源。

    新组件沿用「创建 → 登记清理 → 写入 state → 探活」顺序。
    URL 为空时跳过对应导入，URL 非空但无法连接时阻止应用启动。
    """
    settings = app.state.settings
    timeout = settings.dependency_timeout_seconds
    try:
        async with AsyncExitStack() as cleanup:
            if settings.database_url:
                try:
                    from app.db.session import check_database, create_database

                    engine, session_factory = create_database(settings.database_url)
                except ModuleNotFoundError as exc:
                    if exc.name != "sqlalchemy":
                        raise
                    raise RuntimeError(
                        "Database support is missing. Run: uv sync --extra db"
                    ) from None
                # 必须在探活之前登记：数据库或后续组件失败也会关闭 engine。
                cleanup.push_async_callback(engine.dispose)
                app.state.db_engine = engine
                app.state.db_session_factory = session_factory
                try:
                    async with asyncio.timeout(timeout):
                        await check_database(engine)
                except Exception:
                    raise RuntimeError("Database startup check failed") from None

            if settings.redis_url:
                try:
                    from app.core.redis import create_redis
                except ModuleNotFoundError as exc:
                    if exc.name != "redis":
                        raise
                    raise RuntimeError(
                        "Redis support is missing. Run: uv sync --extra redis"
                    ) from None
                client = create_redis(settings.redis_url, timeout)
                cleanup.push_async_callback(client.aclose, close_connection_pool=True)
                app.state.redis_client = client
                try:
                    async with asyncio.timeout(timeout):
                        if not await client.ping():
                            raise RuntimeError("Redis did not acknowledge PING")
                except Exception:
                    raise RuntimeError("Redis startup check failed") from None

            # 运行期间资源通过 app.state 供依赖注入使用，关闭时 ExitStack 逆序清理。
            yield
    finally:
        app.state.db_engine = None
        app.state.db_session_factory = None
        app.state.redis_client = None
