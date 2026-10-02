# FastAPI 项目脚手架

基于 Python 3.12、FastAPI 和 uv。默认提供健康检查、统一响应、异常处理、请求日志和
配置管理；数据库与 Redis 按需安装、按 URL 启用。

## 快速开始

将脚手架中的可提交文件作为新项目根目录，包含 `.env.example`、`.python-version` 和
`uv.lock`。排除 `.venv`、缓存、数据库文件与测试临时目录，然后初始化新仓库：

```bash
git init
uv sync
uv run uvicorn app.main:app --reload
```

修改 `pyproject.toml` 中的项目名和描述后，运行 `uv lock`。
`uv.lock` 固定依赖版本，应随代码提交；`uv sync` 根据它创建本项目的 `.venv`。

访问：

- 接口文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`
- 就绪检查：`http://localhost:8000/ready`

`/health` 返回：

```json
{"statusCode":200,"status":"success","data":{"status":"ok"},"messages":""}
```

## 变更 Python 版本

默认运行 Python 3.12。更换版本时，区分实际运行版本和项目最低支持版本。
例如将运行版本和最低支持版本都升级到 3.13：

| 文件 | 调整内容 |
| --- | --- |
| `.python-version` | 改为 `3.13`，可由下面的 pin 命令完成 |
| `pyproject.toml` | `requires-python = ">=3.13"`，Ruff 的 `target-version = "py313"` |
| `Dockerfile` | 基础镜像改为 `FROM python:3.13-slim` |

先调整 `pyproject.toml` 和 Dockerfile，再在项目根目录执行：

```bash
uv python install 3.13
uv python pin 3.13
uv lock
uv sync --python 3.13
uv run python --version
```

`uv python pin` 写入默认解释器版本，`uv lock` 更新依赖解析，`uv sync` 按目标版本创建或
更新虚拟环境。安装了可选组件时保留所需 extras，例如
`uv sync --python 3.13 --extra db --extra mysql`。Docker 部署需要重新构建镜像。
`uv.lock` 由 uv 生成，不手动编辑，也不复制其他项目的 `.venv`。

如果只把运行环境换成 3.13，仍需要兼容 3.12，则 `requires-python = ">=3.12"` 和
`target-version = "py312"` 保持不变，只调整默认解释器与实际使用的 Docker 镜像。

降到 3.11 或更低版本时还需改写代码：当前 `class ApiResponse[T]` 和
`type DependencyStatus = ...` 使用了 Python 3.12 语法。更低版本也可能需要调整异步 API
及依赖版本，不能只改配置中的版本号。

版本配置参考 [uv 官方文档](https://docs.astral.sh/uv/concepts/projects/config/)。

## 配置

Linux/macOS：

```bash
cp .env.example .env
```

PowerShell：

```powershell
Copy-Item -LiteralPath .env.example -Destination .env
```

配置读取项目根目录的 `.env`，环境变量优先。未创建 `.env` 也可直接启动。

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_NAME` | `FastAPI Application` | 应用及文档名称 |
| `ENVIRONMENT` | `development` | 环境标识 |
| `DEBUG` | `false` | 调试模式，500 响应仍隐藏内部信息 |
| `LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING / ERROR / CRITICAL |
| `LOG_FORMAT` | `console` | console 或 json |
| `CORS_ORIGINS` | `[]` | JSON 数组，例如 `["http://localhost:3000"]` |
| `DATABASE_URL` | 空 | SQLAlchemy 异步连接 URL，空值关闭数据库 |
| `REDIS_URL` | 空 | redis:// 或 rediss://，空值关闭 Redis |
| `DEPENDENCY_TIMEOUT_SECONDS` | `5` | 启动与就绪探活超时，单位秒 |

配置组件 URL 后，必须同时安装对应依赖并保证组件可用，否则应用启动失败并释放已创建的资源。
`/health` 检查 HTTP 服务，`/ready` 检查已启用组件；组件失效时 `/ready` 返回 HTTP 503。

## 接入数据库

`db` extra 只安装 SQLAlchemy 和 Alembic。根据实际数据库选择异步驱动：

| 数据库 | 安装命令 | DATABASE_URL 示例 |
| --- | --- | --- |
| SQLite | `uv sync --extra db --extra sqlite` | `sqlite+aiosqlite:///./app.db` |
| PostgreSQL | `uv sync --extra db --extra postgres` | `postgresql+asyncpg://app:replace-me@localhost:5432/app` |
| MySQL | `uv sync --extra db --extra mysql` | `mysql+aiomysql://app:replace-me@localhost:3306/app?charset=utf8mb4` |

将选用的 URL 写入 `.env`，再带相同 extras 启动。例如 SQLite：

```bash
uv run --extra db --extra sqlite uvicorn app.main:app --reload
```

SQLite 相对路径以命令的工作目录为基准，请在项目根目录执行命令；父目录需已存在且可写。
文件会在首次连接时创建。PostgreSQL、MySQL 的数据库和账号需提前准备，URL 密码中的特殊字符需编码。
其他数据库可自行安装 SQLAlchemy 支持的异步驱动并配置对应 URL。

### 模型与迁移

1. 模型放入 `app/db/models/`，继承 `app.db.base.Base`。
2. 在 `app/db/models/__init__.py` 中显式导入模型，注册到 `Base.metadata`。
3. 生成并审查迁移，再执行升级。以下以 SQLite 为例，其他数据库替换驱动 extra：

```bash
uv run --extra db --extra sqlite alembic revision --autogenerate -m "init"
uv run --extra db --extra sqlite alembic upgrade head
uv run --extra db --extra sqlite alembic check
```

`revision` 比较模型与现有数据库并生成迁移文件，`upgrade` 执行迁移并记录版本。
应用和 Alembic 共用 `DATABASE_URL`。应用启动不建表、不自动迁移；当前模型与迁移目录为空。
SQLite 自动生成使用 batch 模式处理改表。离线 SQL 可用 `alembic upgrade head --sql`；
涉及 SQLite 重建表的迁移通常需要在线执行。

### 在接口中使用会话

通过 `Depends(get_db)` 注入 `AsyncSession`，调用方负责提交事务，依赖负责异常回滚和关闭：

```python
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
```

接口参数使用 `db: DatabaseSession`。写入后调用 `await db.commit()`，或使用
`async with db.begin():` 包含完整写入操作。未提交的修改不会保存。

## 接入 Redis

```bash
uv sync --extra redis
```

配置 `.env`：

```dotenv
REDIS_URL=redis://localhost:6379/0
```

```bash
uv run --extra redis uvicorn app.main:app --reload
```

通过 `Depends(app.core.redis.get_redis)` 注入共享异步客户端。请求结束时不要关闭客户端，
应用生命周期负责关闭连接池。缓存 key、数据格式和缓存策略由具体业务定义。

组合安装示例：

```bash
uv sync --extra db --extra sqlite --extra redis
uv run --extra db --extra sqlite --extra redis uvicorn app.main:app --reload
```

后续 `uv sync` / `uv run` 保留项目所需的 extras；精确同步会移除未选中的可选依赖。

## 新增接口与统一响应

新增接口模块放在 `app/api/endpoints/`，在 `app/api/router.py` 注册其 router。
请求和响应数据模型放在 `app/schemas/`。例如新增 `app/api/endpoints/ping.py`：

```python
from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.common import ApiResponse

router = APIRouter()


class PingData(BaseModel):
    message: str


@router.get("/ping", response_model=ApiResponse[PingData])
async def ping() -> ApiResponse[PingData]:
    return ApiResponse(data=PingData(message="pong"))
```

在 `app/api/router.py` 导入并注册：

```python
from app.api.endpoints.ping import router as ping_router

api_router.include_router(ping_router)
```

所有应用 API，包括健康检查，采用：

```json
{
  "statusCode": 200,
  "status": "success",
  "data": {"message": "pong"},
  "messages": ""
}
```

- `statusCode` 等于实际 HTTP 状态码，Python 模型字段名为 `status_code`。
- `status` 为 `success` 或 `error`；`data` 放返回数据，无数据时使用 `{}`。
- `messages` 为说明或错误字符串，没有说明时为 `""`。
- 非 200 成功响应需同时设置路由/Response 的 HTTP 状态码和模型的 `status_code`。

接口可以抛出 `BadRequestError`、`NotFoundError`、`ConflictError`、`ServiceUnavailableError`
或 `HTTPException`，全局处理器生成统一错误响应。应用异常详情放在 `data.detail`，
422 字段错误放在 `data.errors`，500 只返回通用消息。OpenAPI 保持标准文档格式。

## 日志

```python
import logging

logger = logging.getLogger(__name__)
logger.info("Operation completed", extra={"operation": "example"})
```

控制台格式为 `时间 | 级别 | logger | request_id=... | 消息`；访问日志追加请求路径、状态码和耗时。
`LOG_FORMAT=json` 输出结构化日志。请求 ID 通过 `X-Request-ID` 接收和返回，
用于关联一次请求的日志，并发请求各自保存日志上下文。

## Docker

Compose 只定义 `app`，不创建数据库、Redis 或数据卷：

```bash
docker compose up --build -d
docker compose logs app
docker compose down
```

连接外部组件时在 `.env` 设置 `DATABASE_URL` / `REDIS_URL` 和所需的构建参数，例如：

```dotenv
UV_EXTRAS=--extra db --extra mysql --extra redis
```

容器内 `localhost` 指向容器自身。连接宿主机上的服务时，Docker Desktop 可使用
`host.docker.internal`；Linux 可按部署环境设置地址或额外的 host-gateway 映射。
数据库服务需允许容器网络访问。然后重新执行 `docker compose up --build -d`。

单独构建：

```bash
docker build --build-arg "UV_EXTRAS=--extra db --extra mysql" -t my-api .
```

镜像不复制 `.env`，使用非 root 用户运行。迁移需要对应 db/驱动 extras，并显式执行：

```bash
docker compose exec app alembic upgrade head
```

使用容器内 SQLite 时，按部署需要添加可写目录挂载并使用绝对 URL
（例如 `sqlite+aiosqlite:////data/app.db`）；未挂载的数据库文件不具备容器重建后的持久性。

## 开发与部署

开发依赖通过 `uv sync` 安装，格式与静态检查命令：

```bash
uv run ruff check .
uv run ruff format .
```

生产依赖安装使用 `uv sync --frozen --no-dev`，添加实际需要的 extras。
