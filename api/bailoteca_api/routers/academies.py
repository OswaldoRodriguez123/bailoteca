from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query

from bailoteca_api.db import get_conn
from bailoteca_api.schemas import (
    AcademyPage,
    ComunaList,
    RegionList,
    RegionOption,
    StyleList,
)
from bailoteca_shared.db import (
    SORTS,
    get_academy_by_slug,
    list_academies as query_academies,
    list_comunas as query_comunas,
    list_styles as query_styles,
)
from bailoteca_shared.regions import REGIONS, REGION_SLUGS
from bailoteca_shared.schema import Academy

router = APIRouter(tags=["academies"])

_STYLE_RE = re.compile(r"^[a-z0-9-]+$")
_REGION_TOKENS = REGION_SLUGS | {"all"}


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _clean_region(value: str | None) -> str | None:
    v = _clean(value)
    if v is not None and v not in _REGION_TOKENS:
        raise HTTPException(
            status_code=422,
            detail="El parámetro region no es válido",
        )
    return v


def _clean_sort(value: str | None) -> str:
    v = _clean(value)
    if v is None or v not in SORTS:
        raise HTTPException(
            status_code=422,
            detail="El parámetro sort no es válido",
        )
    return v


def _clean_coords(
    sort: str,
    lat: float | None,
    lng: float | None,
) -> tuple[float | None, float | None]:
    if sort != "cercanas":
        return None, None
    # Range is enforced by Query(ge=-90..90 / ge=-180..180) in the caller;
    # this only enforces presence for cercanas.
    if lat is None or lng is None:
        raise HTTPException(
            status_code=422,
            detail="El parámetro sort=cercanas requiere lat y lng",
        )
    return lat, lng


@router.get("/academies", response_model=AcademyPage)
def list_academies(
    comuna: str | None = Query(None, max_length=100),
    style: str | None = Query(None, max_length=100),
    q: str | None = Query(None, max_length=100),
    region: str | None = Query(None, max_length=50),
    sort: str = Query("destacadas", max_length=20),
    lat: float | None = Query(None, ge=-90, le=90),
    lng: float | None = Query(None, ge=-180, le=180),
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(20, ge=1, le=100),
    conn=Depends(get_conn),
) -> AcademyPage:
    comuna = _clean(comuna)
    style = _clean(style)
    q = _clean(q)
    region = _clean_region(region)
    sort = _clean_sort(sort)
    lat, lng = _clean_coords(sort, lat, lng)

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
        region=region,
        limit=page_size,
        offset=(page - 1) * page_size,
        sort=sort,
        lat=lat,
        lng=lng,
    )
    return AcademyPage(
        items=rows,
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/academies/{slug}", response_model=Academy)
def get_academy(slug: str, conn=Depends(get_conn)) -> Academy:
    academy = get_academy_by_slug(conn, slug)
    if academy is None:
        raise HTTPException(
            status_code=404,
            detail="Academia no encontrada",
        )
    return Academy.model_validate(academy)


@router.get("/styles", response_model=StyleList)
def list_styles(conn=Depends(get_conn)) -> StyleList:
    return StyleList(items=query_styles(conn))


@router.get("/regions", response_model=RegionList)
def list_regions() -> RegionList:
    return RegionList(
        items=[RegionOption(slug=s, name=n) for s, n in REGIONS]
    )


@router.get("/comunas", response_model=ComunaList)
def list_comunas(
    region: str = Query("metropolitana", max_length=50),
    conn=Depends(get_conn),
) -> ComunaList:
    region = _clean_region(region)
    return ComunaList(items=query_comunas(conn, region=region))
