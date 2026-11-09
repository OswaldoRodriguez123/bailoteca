from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query

from bailoteca_api.db import get_conn
from bailoteca_api.schemas import AcademyPage
from bailoteca_shared.db import (
    get_academy_by_slug,
    list_academies as query_academies,
    list_comunas as query_comunas,
    list_styles as query_styles,
)

router = APIRouter(tags=["academies"])

_STYLE_RE = re.compile(r"^[a-z0-9-]+$")


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


@router.get("/academies", response_model=AcademyPage)
def list_academies(
    comuna: str | None = Query(None, max_length=100),
    style: str | None = Query(None, max_length=100),
    q: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    conn=Depends(get_conn),
) -> AcademyPage:
    comuna = _clean(comuna)
    style = _clean(style)
    q = _clean(q)

    if q is not None and len(q) < 2:
        raise HTTPException(
            status_code=422,
            detail="El parámetro q debe tener al menos 2 caracteres",
        )
    if style is not None and not _STYLE_RE.match(style):
        raise HTTPException(
            status_code=422,
            detail="El parámetro style no es válido",
        )

    rows, total = query_academies(
        conn,
        comuna=comuna,
        style=style,
        q=q,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return AcademyPage(
        items=rows,
        page=page,
        page_size=page_size,
        total=total,
    )
