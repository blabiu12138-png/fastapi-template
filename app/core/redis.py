"""可选异步 Redis 支持，客户端生命周期由应用管理。"""

from fastapi import Request
from redis.asyncio import Redis

from app.core.exceptions import ServiceUnavailableError


def create_redis(url: str, timeout: float) -> Redis:
    """创建应用共享客户端；lifespan 执行 PING 并在退出时关闭连接池。

    decode_responses=True 让字符串命令返回 str；二进制数据业务可按需调整。
    本模块不预设缓存 key、序列化方式或锁规则。
    """
    return Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=timeout,
        socket_timeout=timeout,
        max_connections=50,
    )


async def get_redis(request: Request) -> Redis:
    """接口通过 Depends(get_redis) 取共享客户端，请求结束时不要关闭它。"""
    client = request.app.state.redis_client
    if client is None:
        raise ServiceUnavailableError("Redis is not configured")
    return client
