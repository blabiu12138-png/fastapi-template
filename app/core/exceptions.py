"""通用应用异常，不包含账号或领域业务规则。"""

from typing import Any


class ApplicationError(Exception):
    status_code = 400
    message = "Request failed"

    def __init__(self, message: str | None = None, *, detail: Any = None) -> None:
        self.message = message or self.message
        self.detail = detail
        super().__init__(self.message)


class BadRequestError(ApplicationError):
    message = "Invalid request"


class NotFoundError(ApplicationError):
    status_code = 404
    message = "Resource not found"


class ConflictError(ApplicationError):
    status_code = 409
    message = "Resource conflict"


class ServiceUnavailableError(ApplicationError):
    status_code = 503
    message = "Service unavailable"
