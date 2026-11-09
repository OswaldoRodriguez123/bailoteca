from __future__ import annotations

from pydantic import BaseModel

from bailoteca_shared.schema import Academy


class AcademyPage(BaseModel):
    items: list[Academy]
    page: int
    page_size: int
    total: int
