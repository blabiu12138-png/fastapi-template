FROM ghcr.io/astral-sh/uv:0.11.29 AS uv
FROM python:3.12-slim

COPY --from=uv /uv /uvx /bin/
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

# 按项目需要选择驱动，例如 --build-arg UV_EXTRAS="--extra db --extra mysql"
ARG UV_EXTRAS=""
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev ${UV_EXTRAS}

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
