"""FastAPI app factory (docs/components/05 §7.4).

Mounts routers under /api, installs CORS + the uniform error envelope, and a
minimal lifespan. Migrations + conditional seeding run in the container
entrypoint (spec #7 §3) before uvicorn starts — not here — so startup stays
light and tests aren't double-migrated.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.api.routers import admin, chat, conversations, health
from app.core.config import get_settings
from app.core.logging import setup_logging


def _install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def _http_exc(_: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            envelope = {"error": detail}
        else:
            envelope = {"error": {"code": "error", "message": str(detail)}}
        return JSONResponse(envelope, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            {"error": {"code": "validation_error", "message": "Invalid request."}},
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def _unexpected_exc(_: Request, exc: Exception) -> JSONResponse:
        # Details are logged, never returned.
        return JSONResponse(
            {"error": {"code": "internal_error", "message": "An unexpected error occurred."}},
            status_code=500,
        )


@asynccontextmanager
async def _lifespan(_: FastAPI):
    setup_logging()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Refund Agent API", version="0.1.0", lifespan=_lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["GET", "POST"],
        allow_credentials=False,
        allow_headers=["*"],
    )

    for module in (health, conversations, chat, admin):
        app.include_router(module.router, prefix="/api")

    _install_error_handlers(app)
    return app


app = create_app()
