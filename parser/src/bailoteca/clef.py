"""Triaje de candidatos con Cloudflare Clef (Workers AI).

Juzga, con el texto real de la página, si el candidato es una academia de
salsa/bachata en la Región Metropolitana. Es fail-open: cualquier error deja
pasar el candidato para no perder academias reales.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from bailoteca.enrich import Enriched
from bailoteca.models import Candidate

MODEL = "@cf/cloudflare/clef-flash"
DEFAULT_BASE = "https://api.cloudflare.com/client/v4"
THRESHOLD = 0.5

QUESTIONS = {
    "academia": {
        "type": "noul",
        "instructions": (
            "¿Es la ficha o sitio de una academia o escuela de baile, no un "
            "directorio, blog, evento, grupo, video, canción o restaurante?"
        ),
    },
    "salsa": {
        "type": "noul",
        "instructions": (
            "¿Enseña salsa o bachata (no solo otros estilos como ballet, "
            "urbano, pole o rock)?"
        ),
    },
    "santiago": {
        "type": "noul",
        "instructions": (
            "¿Está ubicada en la Región Metropolitana de Santiago de Chile "
            "(no en otra ciudad o país)?"
        ),
    },
}


class HttpPost(Protocol):
    def post(self, url: str, headers: dict, json: dict): ...


@dataclass(frozen=True)
class Triage:
    accepted: bool
    score: float | None
    error: str | None = None


def build_snippet(enriched: Enriched) -> str:
    text = f"{enriched.description or ''} {(enriched.text or '')[:600]}"
    return " ".join(text.split())[:700]


def _probability(value) -> float:
    if isinstance(value, dict):
        value = value.get("probability", value.get("noul"))
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


class ClefTriage:
    def __init__(
        self,
        http: HttpPost,
        account_id: str,
        token: str,
        base: str = DEFAULT_BASE,
        threshold: float = THRESHOLD,
    ) -> None:
        self._http = http
        self._account_id = account_id
        self._token = token
        self._base = base.rstrip("/")
        self._threshold = threshold

    def evaluate(self, candidate: Candidate, enriched: Enriched) -> Triage:
        state = {
            "name": candidate.name,
            "url": candidate.url,
            "comuna": candidate.comuna,
            "snippet": build_snippet(enriched),
        }
        body = {"model": "clef-flash", "state": state, "questions": QUESTIONS}
        url = f"{self._base}/accounts/{self._account_id}/ai/run/{MODEL}"
        try:
            response = self._http.post(
                url,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            answers = response.json()["result"]["answers"]
            score = min(
                _probability(answers[key])
                for key in ("academia", "salsa", "santiago")
            )
        except Exception as exc:  # fail-open: nunca perder un candidato
            return Triage(accepted=True, score=None, error=str(exc))
        return Triage(accepted=score >= self._threshold, score=score)
