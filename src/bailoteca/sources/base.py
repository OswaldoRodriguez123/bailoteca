from __future__ import annotations

from typing import Protocol, runtime_checkable

from bailoteca.models import Candidate

COMUNAS = [
    "Santiago",
    "Providencia",
    "La Florida",
    "Ñuñoa",
    "San Miguel",
    "Puente Alto",
    "Maipú",
    "La Cisterna",
    "Independencia",
    "Las Condes",
]


@runtime_checkable
class Source(Protocol):
    name: str

    def discover(self) -> list[Candidate]: ...
