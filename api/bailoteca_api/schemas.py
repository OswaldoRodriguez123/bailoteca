from __future__ import annotations

from pydantic import BaseModel

from bailoteca_shared.schema import Academy


class AcademyPage(BaseModel):
    items: list[Academy]
    page: int
    page_size: int
    total: int


class StyleOption(BaseModel):
    slug: str
    name: str
    sort: int


class StyleList(BaseModel):
    items: list[StyleOption]


class ComunaList(BaseModel):
    items: list[str]
