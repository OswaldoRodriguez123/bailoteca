from __future__ import annotations

from fastapi import APIRouter, Request, Response

from bailoteca_api.db import check_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request, response: Response) -> dict[str, str]:
    if check_db(request.app.state.settings):
        return {"status": "ok", "database": "ok"}
    response.status_code = 503
    return {"status": "degraded", "database": "error"}
