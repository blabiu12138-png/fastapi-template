"""与应用共用 Settings 和元数据，不在 INI 内存储连接凭据。"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection, make_url

from alembic import context
from app.core.config import Settings
from app.db import models  # noqa: F401 -- 注册新项目显式导入的 ORM 模型
from app.db.base import Base
from app.db.session import create_database_engine

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

settings = Settings()
if not settings.database_url:
    raise RuntimeError("Set DATABASE_URL before running Alembic")

# 每个模型都要在 app.db.models 中导入，自动生成才能比较到其表结构。
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """upgrade head --sql 输出 SQL，不建立连接；SQLite 重建表需要在线迁移。"""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=make_url(settings.database_url).get_backend_name() == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """将异步连接桥接给 Alembic；SQLite 改表使用批处理迁移。"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """连接 DATABASE_URL 指定的数据库，执行迁移后关闭全部连接。"""
    engine = create_database_engine(settings.database_url, poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
