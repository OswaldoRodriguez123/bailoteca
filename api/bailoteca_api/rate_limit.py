from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def client_ip(request: Request) -> str:
    # Vercel sobrescribe x-forwarded-for con la IP pública del cliente y
    # expone la misma vista en x-real-ip y x-vercel-forwarded-for; este último
    # se conserva aunque Vercel esté detrás de un proxy anterior. Detrás de un
    # proxy genérico que AÑADE (append), el último hop es el que observó el
    # proxy más externo; todo lo anterior vino del cliente y no es confiable.
    # La documentación de Vercel indica que x-forwarded-for se sobrescribe
    # (planes Enterprise pueden activar un proxy confiable).
    for header in ("x-vercel-forwarded-for", "x-real-ip"):
        raw = request.headers.get(header)
        if raw:
            ip = raw.split(",")[-1].strip()
            if ip:
                return ip
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        if hops:
            return hops[-1]
    return get_remote_address(request)


def build_limiter(limit: str) -> Limiter:
    # application_limits aplica un presupuesto agregado por cliente a todas
    # las rutas (no un límite por endpoint y por cliente).
    return Limiter(
        key_func=client_ip,
        application_limits=[limit],
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
