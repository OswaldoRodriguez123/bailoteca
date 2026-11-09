from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return get_remote_address(request)


def build_limiter(limit: str) -> Limiter:
    return Limiter(
        key_func=client_ip,
        default_limits=[limit],
        storage_uri="memory://",
        headers_enabled=True,
    )


def rate_limit_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    response = JSONResponse(
        {"detail": "Demasiadas solicitudes. Intenta de nuevo más tarde."},
        status_code=429,
    )
    return request.app.state.limiter._inject_headers(
        response, request.state.view_rate_limit
    )
