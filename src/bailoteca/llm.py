"""Cliente LLM opcional (Gemini) con degradación silenciosa a reglas."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

DEFAULT_MODELS = ["gemini-2.0-flash", "gemini-2.0-flash-lite"]
RETRYABLE_STATUS = {500, 502, 503, 504}


@dataclass(frozen=True)
class StyleHit:
    slug: str
    confidence: float
    quote: str | None = None
    disputed: bool = False


class LLM(Protocol):
    def classify_styles(self, text: str, slugs: list[str]) -> list[StyleHit] | None: ...


class HttpPost(Protocol):
    def post(self, url: str, headers: dict, json: dict): ...


class HttpxPost:
    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    def post(self, url: str, headers: dict, json: dict):
        import httpx

        return httpx.post(url, headers=headers, json=json, timeout=self.timeout)


PROMPT = """Eres un asistente que clasifica academias de baile.

Texto de la academia:
---
{text}
---

Estilos permitidos (usa exactamente estos slugs): {slugs}

Devuelve SOLO un objeto JSON con esta forma:
{{"hits": [{{"slug": "...", "confidence": 0.0, "quote": "..."}}]}}

Reglas:
- "confidence" va entre 0 y 1.
- "quote" debe ser una cita literal del texto que justifique el estilo.
- Si el texto habla de salsa como comida o de otra cosa que no sea bailar,
  devuelve {{"hits": []}}.
"""


class GeminiLLM:
    def __init__(
        self,
        api_key: str,
        http: HttpPost,
        models: list[str] | None = None,
    ):
        self.api_key = api_key
        self.http = http
        self.models = models or DEFAULT_MODELS

    def classify_styles(self, text: str, slugs: list[str]) -> list[StyleHit] | None:
        if not self.api_key:
            return None
        prompt = PROMPT.format(text=text, slugs=", ".join(slugs))
        for model in self.models:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent?key={self.api_key}"
            )
            try:
                response = self.http.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"responseMimeType": "application/json"},
                    },
                )
            except Exception:
                return None
            status = getattr(response, "status_code", 0)
            if status == 429:
                return None
            if status in RETRYABLE_STATUS:
                continue
            if status != 200:
                return None
            try:
                return self._parse(response.json(), slugs)
            except Exception:
                return None
        return None

    @staticmethod
    def _parse(payload: dict, slugs: list[str]) -> list[StyleHit]:
        body = payload["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(body)
        hits: list[StyleHit] = []
        for hit in data.get("hits", []):
            slug = hit.get("slug")
            if slug not in slugs:
                continue
            try:
                confidence = float(hit.get("confidence"))
            except (TypeError, ValueError):
                continue
            if not 0.0 <= confidence <= 1.0:
                continue
            quote = hit.get("quote")
            hits.append(
                StyleHit(
                    slug=slug,
                    confidence=confidence,
                    quote=quote if isinstance(quote, str) else None,
                )
            )
        return hits
