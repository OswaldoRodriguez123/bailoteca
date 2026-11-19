"""Cliente LLM opcional (Gemini) con degradación silenciosa a reglas."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

DEFAULT_MODELS = ["gemini-3.1-flash-lite", "gemini-2.5-flash"]
RETRYABLE_STATUS = {500, 502, 503, 504}


@dataclass(frozen=True)
class DescriptionResult:
    """Resultado tri-estado de la limpieza de descripción.

    ok: ``text`` es la descripción limpia. noise: el texto crudo es ruido
    puro (o la salida degeneró) → omitir la descripción, nunca publicar la
    basura. failure: error transitorio/contrato (sin API key, HTTP no-200,
    JSON inválido) → el llamador conserva el texto crudo como respaldo.
    """

    status: str  # "ok" | "noise" | "failure"
    text: str | None = None


@dataclass(frozen=True)
class StyleHit:
    slug: str
    confidence: float
    quote: str | None = None
    disputed: bool = False


class LLM(Protocol):
    def classify_styles(self, text: str, slugs: list[str]) -> list[StyleHit] | None: ...
    def normalize_identity(self, text: str, fallback_name: str) -> str | None: ...
    def normalize_description(self, text: str) -> DescriptionResult: ...


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


PROMPT_DESCRIPTION = """Eres un asistente que limpia la descripción pública de una academia de baile para un directorio.

Texto crudo de la academia (suele venir del og:description de Instagram/Facebook, con ruido de seguidores/posts):
---
{text}
---

Devuelve SOLO un objeto JSON con esta forma:
{{"description": "..."}}

Reglas:
- Máximo 2 frases, en español, tono informativo y neutro.
- Elimina contadores ("31K seguidores", "204 Posts"), líneas de bio, emojis decorativos, hashtags, links, CTA ("reserva", "contacta ahora") y handles @usuario.
- Conserva lo verificable: qué enseña, dónde queda, niveles, modalidad (grupales/particulares).
- No inventes datos que no aparecen en el texto (dirección, horarios, teléfonos, estilos que no están).
- Si el texto es puro ruido y no queda nada útil, responde {{"description": null}}.
"""

PROMPT_IDENTITY = """Eres un asistente que extrae el nombre comercial corto de una academia de baile.

Texto de la academia:
---
{text}
---

Nombre tal como viene (suele ser un título SEO largo): {fallback}

Devuelve SOLO un objeto JSON con esta forma:
{{"name": "Nombre Corto"}}

Reglas:
- "name" debe ser el nombre comercial del negocio (ej: "Mushin", "Casa del Mambo", "JSD Academy", "Fred Astaire Santiago").
- No incluyas descriptores ("Clases de salsa", "| Santiago", "Academia de", "| Oficial").
- Máximo 6 palabras. Sin guiones largos, barras, paréntesis con hashtags.
- Si no puedes determinar, responde {{"name": "{fallback}"}} con el mismo nombre tal cual.
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

    def _query_json(self, prompt: str) -> dict | None:
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
                body = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(body)
            except Exception:
                return None
        return None

    def classify_styles(self, text: str, slugs: list[str]) -> list[StyleHit] | None:
        if not self.api_key:
            return None
        prompt = PROMPT.format(text=text, slugs=", ".join(slugs))
        data = self._query_json(prompt)
        if not data:
            return None
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

    def normalize_identity(self, text: str, fallback_name: str) -> str | None:
        if not self.api_key:
            return None
        prompt = PROMPT_IDENTITY.format(text=(text or "")[:800], fallback=fallback_name)
        data = self._query_json(prompt)
        if not isinstance(data, dict):
            return None
        name = data.get("name")
        if not isinstance(name, str):
            return None
        cleaned = " ".join(name.split()).strip(" -–|")
        if not 1 <= len(cleaned) <= 60:
            return None
        return cleaned

    def normalize_description(self, text: str) -> DescriptionResult:
        if not self.api_key:
            return DescriptionResult("failure")
        prompt = PROMPT_DESCRIPTION.format(text=(text or "")[:800])
        data = self._query_json(prompt)
        if not isinstance(data, dict):
            return DescriptionResult("failure")
        if "description" in data and data["description"] is None:
            # Null explícito: el modelo declaró ruido puro.
            return DescriptionResult("noise")
        desc = data.get("description")
        if not isinstance(desc, str):
            return DescriptionResult("failure")
        cleaned = " ".join(desc.split()).strip()
        # Sin mínimo artificial de palabras: el prompt ya descarta ruido
        # (null). Solo se acota longitud para descartar salidas degeneradas
        # o desbordadas — que se tratan como ruido, no como texto publicable.
        if len(cleaned) < 8 or len(cleaned) > 320:
            return DescriptionResult("noise")
        return DescriptionResult("ok", cleaned)
