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
        def get(self, url, params=None):
            return _Response()

    sleeps = []
    monkeypatch.setattr(
        "bailoteca.sources.search.time.sleep",
        lambda seconds: sleeps.append(seconds),
    )
    DuckDuckGoSource(["uno", "dos"], _Http(), delay=1.0).discover()
    assert len(sleeps) == 1
    assert 0.9 <= sleeps[0] <= 1.0
