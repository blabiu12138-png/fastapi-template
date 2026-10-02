"""路由注册入口：导入新模块的 router，再调用 api_router.include_router。"""

from fastapi import APIRouter

from app.api.endpoints.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
