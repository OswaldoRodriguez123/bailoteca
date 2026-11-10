from __future__ import annotations

import logging

import psycopg
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from bailoteca_api.config import Settings, get_settings
from bailoteca_api.db import DatabaseUnavailable
from bailoteca_api.rate_limit import build_limiter, rate_limit_handler
from bailoteca_api.routers import academies, health

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Bailoteca API", version="0.1.0")
    app.state.settings = settings

    limiter = build_limiter(settings.rate_limit)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    @app.exception_handler(DatabaseUnavailable)
    async def database_unavailable_handler(
        request: Request, exc: DatabaseUnavailable
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"detail": "Base de datos no disponible"},
        )

    @app.exception_handler(psycopg.Error)
    async def psycopg_error_handler(
        request: Request, exc: psycopg.Error
    ) -> JSONResponse:
        logger.exception("Error de base de datos")
        return JSONResponse(
            status_code=503,
            content={"detail": "Base de datos no disponible"},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Error no controlado")
        return JSONResponse(
            status_code=500,
            content={"detail": "Error interno"},
        )

    app.include_router(health.router)
    app.include_router(academies.router)
    return app


app = create_app()
