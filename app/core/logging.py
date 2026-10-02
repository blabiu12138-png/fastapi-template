"""标准 logging，统一应用与 Uvicorn 输出。"""

import contextvars
import json
import logging
import sys
from datetime import UTC, datetime

from app.core.config import Settings

# 每个并发请求有独立上下文；ID 只关联日志，不参与权限或数据隔离。
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="server-main"
)
_STANDARD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_FIELDS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(settings: Settings) -> None:
    """应用工厂调用一次，统一标准 logging 与 Uvicorn 输出。

    业务模块使用 logging.getLogger(__name__)；可用 extra 附加结构化字段。
    console 使用 | 分隔，json 输出额外字段和异常堆栈，供日志平台采集。
    配置作用于进程，同一进程多 app 以最后一次调用为准。
    """
    formatter: logging.Formatter
    if settings.log_format == "json":
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | request_id=%(request_id)s | %(message)s"
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(RequestContextFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level)

    for name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
        logger.setLevel(settings.log_level)
    # 请求访问日志由中间件统一记录，避免 Uvicorn 再记录一次。
    logging.getLogger("uvicorn.access").disabled = True
