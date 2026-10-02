"""可选的 SQLAlchemy 异步接入，适用于不同数据库的异步驱动。

安装 db extra 和所需驱动，再配置 DATABASE_URL 即可启用。应用 lifespan 创建
一个 engine / sessionmaker；接口通过 Depends(get_db) 获取独立请求会话。
该模块只由已启用的数据库组件或 Alembic 导入，基础应用不依赖 SQLAlchemy。
"""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, NoSuchModuleError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import Pool

from app.core.exceptions import ServiceUnavailableError


def create_database_engine(url: str, *, poolclass: type[Pool] | None = None) -> AsyncEngine:
    """应用和迁移共用的 engine 创建入口；创建时尚未连接数据库。

    URL 指定方言及异步驱动，例如 sqlite+aiosqlite / postgresql+asyncpg /
    mysql+aiomysql。其他 SQLAlchemy 异步驱动也可在安装后使用。
    不混用各驱动的 connect_args；专用参数可写入驱动支持的 URL 查询参数。
    poolclass 仅供 Alembic 选择 NullPool，应用采用方言自身的默认连接池。
    """
    try:
        database_url = make_url(url)
    except ArgumentError:
        raise RuntimeError("DATABASE_URL must be a valid SQLAlchemy connection URL") from None
    try:
        dialect = database_url.get_dialect(_is_async=True)
    except NoSuchModuleError:
        raise RuntimeError("Install the SQLAlchemy dialect selected by DATABASE_URL") from None
    if not dialect.is_async:
        raise RuntimeError(
            "DATABASE_URL requires an async SQLAlchemy driver, for example "
            "sqlite+aiosqlite, postgresql+asyncpg or mysql+aiomysql"
        )
    try:
        return create_async_engine(database_url, pool_pre_ping=True, poolclass=poolclass)
    except ModuleNotFoundError as exc:
        driver_extras = {"asyncpg": "postgres", "aiosqlite": "sqlite", "aiomysql": "mysql"}
        extra = driver_extras.get(exc.name)
        if extra is None:
            raise
        raise RuntimeError(
            f"Database driver is missing. Run: uv sync --extra db --extra {extra}"
        ) from None


def create_database(url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """创建应用级连接池和会话工厂；启动探活及关闭由 lifespan 负责。"""
    engine = create_database_engine(url)
    # commit 后仍可读取已加载字段，避免响应序列化触发隐式异步查询。
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory


async def check_database(engine: AsyncEngine) -> None:
    """执行跨数据库的最小探活；外层 lifespan / ready 控制检查超时。"""
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """接口使用 Depends(get_db)，会话仅属于当前请求。

    本依赖不自动提交。调用方用 await session.commit() 或
    async with session.begin(): 明确事务边界；异常时回滚，退出时关闭会话。
    后台任务应自行创建会话，不要复用已经结束的请求会话。
    """
    session_factory = request.app.state.db_session_factory
    if session_factory is None:
        raise ServiceUnavailableError("Database is not configured")

    async with session_factory() as session:
        try:
            yield session
        except BaseException:
            await session.rollback()
            raise
