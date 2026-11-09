from bailoteca.clef import ClefTriage, build_snippet
from bailoteca.enrich import Enriched
from bailoteca.models import Candidate


def _candidate():
    return Candidate("Academia X", "https://x.cl", None, "serpapi")


def _enriched(text="", description=None):
    return Enriched(
        _candidate(), "https://x.cl", text, None, None, description=description
    )


class _Resp:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def json(self):
        return self._payload


class _Http:
    def __init__(self, payload=None, error=None):
        self.payload, self.error, self.calls = payload, error, []

    def post(self, url, headers=None, json=None):
        self.calls.append((url, headers, json))
        if self.error:
            raise self.error
        return _Resp(self.payload)


def _payload(a=0.9, s=0.9, g=0.9):
    return {
        "result": {
            "answers": {
                "academia": {"probability": a},
                "salsa": {"noul": s},
                "santiago": g,
            }
        }
    }


def test_accepts_when_min_probability_is_above_threshold():
    triage = ClefTriage(_Http(_payload(0.5, 0.5, 0.5)), "acct", "tok")
    result = triage.evaluate(_candidate(), _enriched())
    assert result.accepted is True
    assert abs(result.score - 0.5) < 1e-9


def test_rejects_when_any_probability_is_below_threshold():
    triage = ClefTriage(_Http(_payload(0.9, 0.9, 0.4)), "acct", "tok")
    assert triage.evaluate(_candidate(), _enriched()).accepted is False


def test_fail_open_on_http_error():
    triage = ClefTriage(_Http(error=TimeoutError("boom")), "acct", "tok")
    result = triage.evaluate(_candidate(), _enriched())
    assert result.accepted is True
    assert result.score is None
    assert "boom" in (result.error or "")


def test_fail_open_on_unparseable_payload():
    triage = ClefTriage(_Http({"result": {}}), "acct", "tok")
    result = triage.evaluate(_candidate(), _enriched())
    assert result.accepted is True
    assert result.error is not None


def test_sends_credentials_and_page_text():
    http = _Http(_payload())
    triage = ClefTriage(http, "acct", "tok")
    triage.evaluate(
        _candidate(), _enriched("   salsa   cubana  " * 80, "Academia de salsa")
    )
    url, headers, body = http.calls[0]
    assert "/accounts/acct/ai/run/@cf/cloudflare/clef-flash" in url
    assert headers["Authorization"] == "Bearer tok"
    snippet = body["state"]["snippet"]
    assert "Academia de salsa" in snippet
    assert len(snippet) <= 700
    assert "salsa cubana" in snippet


def test_build_snippet_without_text_uses_description():
    assert build_snippet(_enriched("", "Solo bachata")).startswith("Solo bachata")


def test_build_snippet_empty_is_empty_string():
    assert build_snippet(_enriched()) == ""
