"""绑定请求 ID，在响应完成后记录访问日志并清理上下文。"""

import logging
import re
import time
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.exception_handlers import unhandled_error_handler
from app.core.logging import request_id_var

logger = logging.getLogger("app.access")
_REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,128}")


class RequestContextMiddleware:
    """关联请求、响应和日志，并在访问日志写完后清理 ContextVar。

    复用格式合法的 X-Request-ID，否则生成 ID；始终在响应头返回该 ID。
    使用原生 ASGI 中间件，避免额外读取请求体，流式响应同样经过 send。
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        supplied_id = Headers(scope=scope).get("X-Request-ID", "")
        request_id = supplied_id if _REQUEST_ID_PATTERN.fullmatch(supplied_id) else uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_var.set(request_id)
        started_at = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_with_context(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_started = True
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            try:
                await self.app(scope, receive, send_with_context)
            except Exception as exc:
                # 已发送响应头后不能再改写响应；交给服务器处理此类故障。
                if response_started:
                    raise
                response = await unhandled_error_handler(Request(scope), exc)
                await response(scope, receive, send_with_context)
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            try:
                logger.info(
                    "%s %s | %s | %.2fms",
                    scope["method"],
                    scope["path"],
                    status_code,
                    duration_ms,
                    extra={
                        "method": scope["method"],
                        "path": scope["path"],
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                    },
                )
            finally:
                request_id_var.reset(token)
