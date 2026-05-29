# Backend image — see docs/components/07-infra.md §4.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN useradd -m appuser
COPY apps/backend/pyproject.toml ./
RUN pip install --no-cache-dir . && pip install --no-cache-dir alembic uvicorn[standard]
COPY apps/backend/ ./
RUN chmod +x entrypoint.sh && chown -R appuser /app
USER appuser
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
