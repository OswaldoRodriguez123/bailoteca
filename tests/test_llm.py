import json

from directorio_baile.llm import GeminiLLM, StyleHit


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
