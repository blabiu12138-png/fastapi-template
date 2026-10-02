from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiResponse[T](BaseModel):
    """接口声明 response_model=ApiResponse[数据模型] 并返回 ApiResponse(data=...)。

    JSON 字段采用 statusCode，需与路由或 Response 的 HTTP 状态码一致。
    错误响应由异常处理器生成；无说明时 messages 留空。
    """

    model_config = ConfigDict(populate_by_name=True)

    status_code: int = Field(default=200, alias="statusCode")
    status: Literal["success", "error"] = "success"
    data: T
    messages: str = ""
