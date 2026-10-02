"""错误码采用 HTTP 状态码，500 响应始终隐藏内部异常。"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.core.exceptions import ApplicationError
from app.schemas.common import ApiResponse

logger = logging.getLogger(__name__)


def error_response(
    request: Request,
    status_code: int,
    message: str,
    data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    if status_code == 500:
        message = "Internal server error"
        data = {}
    response_headers = dict(headers or {})
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        response_headers["X-Request-ID"] = request_id
    body = ApiResponse[dict[str, Any]](
        status_code=status_code,
        status="error",
        data=data if data is not None else {},
        messages=message,
    )
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(body),
        headers=response_headers,
    )


async def application_error_handler(request: Request, exc: ApplicationError) -> JSONResponse:
    data = {} if exc.detail is None else {"detail": exc.detail}
    return error_response(request, exc.status_code, exc.message, data)


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for error in exc.errors():
        errors.append(
            {
                "field": ".".join(str(part) for part in error["loc"]),
                "message": error["msg"],
            }
        )
    return error_response(request, 422, "Request validation failed", {"errors": errors})


async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "HTTP request failed"
    data = {} if isinstance(exc.detail, str) else {"detail": exc.detail}
    if exc.status_code >= 500:
        message = "Internal server error"
        data = {}
    return error_response(request, exc.status_code, message, data, headers=exc.headers)


async def response_validation_error_handler(
    request: Request, exc: ResponseValidationError
) -> JSONResponse:
    logger.error("Response validation failed", exc_info=exc)
    return error_response(request, 500, "Internal server error")


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled application error", exc_info=exc)
    return error_response(request, 500, "Internal server error")


def setup_exception_handlers(app: FastAPI) -> None:
    """在应用工厂注册一次；接口抛出 ApplicationError 或 HTTPException 即可。

    客户端统一收到 ApiResponse，422 详情位于 data.errors。
    500 的堆栈只写服务端日志，响应始终使用通用消息。
    """
    app.add_exception_handler(ApplicationError, application_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(ResponseValidationError, response_validation_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
