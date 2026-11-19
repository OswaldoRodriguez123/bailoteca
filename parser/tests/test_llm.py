import json

from bailoteca.llm import GeminiLLM, StyleHit


class _Response:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


class _Http:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def post(self, url, headers, json):
        self.calls += 1
        return self.responses.pop(0)


def _gemini_body(hits):
    return {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps({"hits": hits})}]}}
        ]
    }


def test_gemini_parses_hits():
    http = _Http(
        [
            _Response(
                200,
                _gemini_body(
                    [
                        {
                            "slug": "salsa-cubana",
                            "confidence": 0.91,
                            "quote": "salsa cubana",
                        }
                    ]
                ),
            )
        ]
    )
    llm = GeminiLLM("key", http)
    hits = llm.classify_styles("clases de salsa cubana", ["salsa-cubana"])
    assert hits == [StyleHit("salsa-cubana", 0.91, "salsa cubana")]


def test_gemini_falls_back_on_503():
    http = _Http([_Response(503, {}), _Response(200, _gemini_body([]))])
    llm = GeminiLLM("key", http, models=["a", "b"])
    assert llm.classify_styles("texto", ["mambo"]) == []
    assert http.calls == 2


def test_gemini_stops_on_429():
    http = _Http([_Response(429, {})])
    llm = GeminiLLM("key", http, models=["a", "b"])
    assert llm.classify_styles("texto", ["mambo"]) is None
    assert http.calls == 1


def test_gemini_returns_none_without_key():
    assert GeminiLLM("", _Http([])).classify_styles("texto", ["mambo"]) is None


def _gemini_description_body(desc):
    return {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps({"description": desc})}]}}
        ]
    }


def test_gemini_normalizes_description():
    desc = (
        "Academia de salsa y bachata en Providencia. "
        "Clases grupales para todos los niveles."
    )
    http = _Http([_Response(200, _gemini_description_body(desc))])
    llm = GeminiLLM("key", http)
    raw = (
        "16K Followers, 277 Following, 204 Posts - Cesár Yáñez Muñoz "
        "(@rumbadecalle) on Instagram: Clases de Ritmos Latinos Plaza Ñuñoa"
    )
    assert llm.normalize_description(raw) == desc


def test_gemini_description_none_on_noise():
    http = _Http([_Response(200, _gemini_description_body(None))])
    llm = GeminiLLM("key", http)
    assert llm.normalize_description("puro ruido, nada que ver") is None


def test_gemini_description_rejects_junk():
    http = _Http([_Response(200, _gemini_description_body("ok"))])
    llm = GeminiLLM("key", http)
    assert llm.normalize_description("texto") is None


def test_gemini_description_without_key():
    assert GeminiLLM("", _Http([])).normalize_description("texto") is None


def test_gemini_description_accepts_short_valid():
    http = _Http([_Response(200, _gemini_description_body("Salsa y bachata."))])
    llm = GeminiLLM("key", http)
    assert llm.normalize_description("texto de la academia") == "Salsa y bachata."
