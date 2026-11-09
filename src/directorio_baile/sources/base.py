from __future__ import annotations

from typing import Protocol, runtime_checkable

from directorio_baile.models import Candidate

COMUNAS = [
    "Santiago",
    "Providencia",
    "Las Condes",
    "Ñuñoa",
    "Maipú",
    "La Florida",
    "Puente Alto",
    "San Miguel",
    "Recoleta",
    "Independencia",
    "Estación Central",
    "La Reina",
    "Macul",
    "Peñalolén",
    "Vitacura",
]


@runtime_checkable
class Source(Protocol):
    name: str

    def discover(self) -> list[Candidate]: ...
