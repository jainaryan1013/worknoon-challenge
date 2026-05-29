# Test-runner image — installs dev deps (pytest etc.) on top of the runtime deps.
# Source is bind-mounted by docker-compose.test.yml, so this image only needs the
# installed dependencies; the mount provides app/ and tests/ at runtime.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app
WORKDIR /app
COPY apps/backend/pyproject.toml ./
RUN pip install --no-cache-dir ".[dev]" && pip install --no-cache-dir alembic
COPY apps/backend/ ./
CMD ["pytest", "-q"]
