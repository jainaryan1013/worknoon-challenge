"""GET /api/health — db + llm readiness (docs/components/05 §6)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.deps import get_settings_dep
from app.core.config import Settings
from app.db.session import SessionLocal

router = APIRouter()


@router.get("/health")
def health(settings: Settings = Depends(get_settings_dep)) -> JSONResponse:
    db_ok = True
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - any DB failure means not ready
        db_ok = False

    payload = {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "down",
        "llm_configured": settings.llm_configured,
    }
    # 503 when DB is down so the compose healthcheck gates dependents.
    return JSONResponse(payload, status_code=200 if db_ok else 503)
