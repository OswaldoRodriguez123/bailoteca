import json
from pathlib import Path

from bailoteca.sources.osm import parse_overpass
from bailoteca.sources.search import build_queries, parse_ddg_html
from bailoteca.sources.seed import load_seed

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_seed_reads_optional_fields():
    candidates = load_seed(FIXTURES / "seed.csv")
    assert [c.name for c in candidates] == ["Academia Semilla", "Solo Instagram"]
    assert candidates[0].handle == "semilla"
    assert candidates[1].url is None


def test_build_queries():
    assert build_queries(["Providencia"]) == [
        "academia de salsa Providencia",
        "salsa cubana Providencia",
        "salsa en linea Providencia",
        "mambo Providencia",
        "bachata Providencia",
    ]


def test_parse_ddg_html_drops_instagram_posts():
    candidates = parse_ddg_html((FIXTURES / "results.html").read_text())
    assert [c.url for c in candidates] == ["https://nueva.cl/"]


def test_parse_overpass_maps_fields_and_skips_unnamed():
    candidates = parse_overpass(
        json.loads((FIXTURES / "overpass.json").read_text())
    )
    assert len(candidates) == 1
    assert candidates[0].name == "Academia OSM"
    assert candidates[0].raw["address"] == "Av. Test 123"
    assert candidates[0].raw["comuna"] == "Providencia"
    assert candidates[0].handle == "osmacademia"


def test_ddg_source_enforces_delay_between_queries(monkeypatch):
    from bailoteca.sources.search import DuckDuckGoSource

    class _Response:
        status_code = 200
        text = ""

    class _Http:
        def get(self, url, params=None, **kwargs):
            return _Response()

    sleeps = []
    monkeypatch.setattr(
        "bailoteca.sources.search.time.sleep",
        lambda seconds: sleeps.append(seconds),
    )
    DuckDuckGoSource(["uno", "dos"], _Http(), delay=1.0).discover()
    assert len(sleeps) == 1
    assert 0.9 <= sleeps[0] <= 1.0


def test_ddg_source_survives_http_errors_and_passes_timeout():
    from bailoteca.sources.search import DuckDuckGoSource

    calls = []

    class _Http:
        def get(self, url, params=None, **kwargs):
            calls.append(kwargs)
            raise TimeoutError("network colgada")

    result = DuckDuckGoSource(["uno", "dos"], _Http(), delay=0).discover()
    assert result == []
    assert all("timeout" in kw for kw in calls)
    assert all(kw["timeout"] == 10 for kw in calls)


def test_parse_serpapi_json_maps_organic_results():
    from bailoteca.sources.serpapi import parse_serpapi_json

    data = {
        "organic_results": [
            {"title": "BailaSalsa | Academia", "link": "https://bailasalsa.cl/", "snippet": "Clases en Providencia"},
            {"title": "Academia X en Instagram", "link": "https://www.instagram.com/bailasalsa/", "snippet": "IG"},
            {"title": "Post IG", "link": "https://www.instagram.com/p/ABC123/", "snippet": "post"},
            {"title": "", "link": "https://sin-titulo.cl/", "snippet": ""},
        ]
    }
    cands = parse_serpapi_json(data)
    assert [c.name for c in cands] == ["BailaSalsa | Academia", "Academia X en Instagram"]
    assert cands[0].url == "https://bailasalsa.cl/"
    assert cands[0].source == "serpapi"
    assert cands[1].handle == "bailasalsa"


def test_serpapi_source_survives_errors_and_passes_timeout():
    from bailoteca.sources.serpapi import SerpApiSource

    calls = []

    class _Http:
        def get(self, url, params=None, **kwargs):
            calls.append((url, params, kwargs))
            raise TimeoutError("red colgada")

    source = SerpApiSource(["uno", "dos"], api_key="key-123", http=_Http(), delay=0)
    assert source.discover() == []
    assert len(calls) == 2
    assert all(kw["timeout"] == 10 for _, _, kw in calls)
    assert calls[0][1]["api_key"] == "key-123"
    assert calls[0][1]["engine"] == "google"
    assert calls[0][1]["gl"] == "cl"


def _serpapi_http(calls):
    class _Response:
        status_code = 200

        def json(self):
            return {
                "organic_results": [
                    {"title": "Academia Cache", "link": "https://cache.cl/"}
                ]
            }

    class _Http:
        def get(self, url, params=None, **kwargs):
            calls.append(params)
            return _Response()

    return _Http()


def test_serpapi_source_reuses_fresh_cache_without_calling_api(tmp_path):
    from bailoteca.sources.serpapi import SerpApiSource

    calls = []
    first = SerpApiSource(
        ["uno"], api_key="key-1", http=_serpapi_http(calls), delay=0,
        cache_dir=tmp_path,
    )
    assert [c.name for c in first.discover()] == ["Academia Cache"]
    assert len(calls) == 1

    second = SerpApiSource(
        ["uno"], api_key="otra-key", http=_serpapi_http(calls), delay=0,
        cache_dir=tmp_path,
    )
    assert [c.name for c in second.discover()] == ["Academia Cache"]
    assert len(calls) == 1  # la clave de caché no depende de api_key


def test_serpapi_source_refetches_when_cache_is_expired(tmp_path):
    from bailoteca.sources.serpapi import SerpApiSource

    calls = []
    SerpApiSource(
        ["uno"], api_key="k", http=_serpapi_http(calls), delay=0,
        cache_dir=tmp_path,
    ).discover()
    SerpApiSource(
        ["uno"], api_key="k", http=_serpapi_http(calls), delay=0,
        cache_dir=tmp_path, cache_ttl=-1,
    ).discover()
    assert len(calls) == 2


def test_serpapi_source_ignores_corrupt_cache(tmp_path):
    from bailoteca.sources.serpapi import SerpApiSource

    calls = []
    source = SerpApiSource(
        ["uno"], api_key="k", http=_serpapi_http(calls), delay=0,
        cache_dir=tmp_path,
    )
    source.discover()
    for path in (tmp_path / "serpapi").glob("*.json"):
        path.write_text("no es json", encoding="utf-8")

    SerpApiSource(
        ["uno"], api_key="k", http=_serpapi_http(calls), delay=0,
        cache_dir=tmp_path,
    ).discover()
    assert len(calls) == 2


def test_overpass_source_passes_user_agent_and_retries(monkeypatch):
    from bailoteca.sources.osm import OVERPASS_ENDPOINTS, OverpassSource

    fixture = json.loads((FIXTURES / "overpass.json").read_text())
    calls = []
    responses = [
        type("R", (), {"status_code": 502, "json": lambda self: {}}),
        type("R", (), {"status_code": 200, "json": lambda self: fixture}),
    ]
    sleeps = []

    class _Http:
        def post(self, url, content=None, headers=None, timeout=None):
            calls.append((url, headers, timeout))
            return responses.pop(0)()

    monkeypatch.setattr("bailoteca.sources.osm.time.sleep", sleeps.append)
    cands = OverpassSource(http=_Http()).discover()
    assert len(cands) == 1
    assert calls[0][0] == OVERPASS_ENDPOINTS[0]
    assert calls[0][1]["User-Agent"]
    assert calls[0][2] >= 60
    assert sleeps == [5.0]


def test_overpass_source_returns_empty_when_all_attempts_fail(monkeypatch):
    from bailoteca.sources.osm import OverpassSource

    calls = []
    sleeps = []

    class _Http:
        def post(self, url, content=None, headers=None, timeout=None):
            calls.append(url)
            raise TimeoutError("red colgada")

    monkeypatch.setattr("bailoteca.sources.osm.time.sleep", sleeps.append)
    assert OverpassSource(http=_Http()).discover() == []
    import bailoteca.sources.osm as osm_module

    assert len(calls) == len(osm_module.OVERPASS_ENDPOINTS) * osm_module.MAX_ATTEMPTS
    assert sleeps == [5.0] * len(calls)
