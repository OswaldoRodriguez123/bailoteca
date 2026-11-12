"""Pruebas de la convivencia de providers de búsqueda."""

from __future__ import annotations

from pathlib import Path

from bailoteca.config import Config
from bailoteca.models import Candidate
from bailoteca.sources.combined import (
    CombinedSearchSource,
    build_search_source,
    build_search_sources,
)


class _FakeSource:
    def __init__(self, name: str, candidates: list[Candidate], boom: bool = False):
        self.name = name
        self.candidates = candidates
        self.boom = boom
        self.calls = 0

    def discover(self) -> list[Candidate]:
        self.calls += 1
        if self.boom:
            raise RuntimeError("provider caído")
        return self.candidates


def _candidate(url: str) -> Candidate:
    return Candidate(name=url, url=url, handle=None, source="fake")


def _config(**overrides) -> Config:
    values = dict(
        database_url=None,
        gemini_api_key=None,
        serpapi_key=None,
        brave_api_key=None,
        tinyfish_api_key=None,
        cloudflare_account_id=None,
        cloudflare_token=None,
        resend_api_key=None,
        review_to_email=None,
        review_from_email="onboarding@resend.dev",
        supabase_url=None,
        supabase_service_role_key=None,
        cache_dir=Path("data/cache"),
        reports_dir=Path("reports"),
        sources=["seed"],
        search_providers=["brave", "tinyfish", "serpapi"],
    )
    values.update(overrides)
    return Config(**values)


def test_combined_deduplica_urls_y_conserva_orden():
    first = _FakeSource("brave", [_candidate("https://a.cl"), _candidate("https://b.cl")])
    second = _FakeSource("tinyfish", [_candidate("https://B.cl"), _candidate("https://c.cl")])

    combined = CombinedSearchSource([first, second])

    assert [c.url for c in combined.discover()] == [
        "https://a.cl",
        "https://b.cl",
        "https://c.cl",
    ]
    assert first.calls == 1 and second.calls == 1


def test_combined_sigue_si_un_provider_falla():
    caido = _FakeSource("brave", [], boom=True)
    sano = _FakeSource("tinyfish", [_candidate("https://c.cl")])

    combined = CombinedSearchSource([caido, sano])

    assert [c.url for c in combined.discover()] == ["https://c.cl"]
    assert sano.calls == 1


def test_combined_ignora_fuentes_none():
    combined = CombinedSearchSource([None, _FakeSource("brave", [_candidate("https://a.cl")])])

    assert [c.url for c in combined.discover()] == ["https://a.cl"]
    assert bool(combined) is True


def test_combined_vacio_no_es_verdadero():
    assert bool(CombinedSearchSource([])) is False
    assert CombinedSearchSource([]).discover() == []


def test_build_search_source_sin_key_devuelve_none():
    assert build_search_source("brave", ["q"], _config()) is None
    assert build_search_source("tinyfish", ["q"], _config()) is None
    assert build_search_source("serpapi", ["q"], _config()) is None
    assert build_search_source("desconocido", ["q"], _config()) is None


def test_build_search_sources_combina_solo_los_disponibles():
    config = _config(brave_api_key="x", tinyfish_api_key="y")

    combined = build_search_sources(
        ["brave", "tinyfish", "serpapi"], ["q"], config, http=object(), num=3
    )

    assert [source.name for source in combined.sources] == ["brave", "tinyfish"]


def test_config_lee_providers_del_entorno():
    config = Config.from_env(
        {
            "BAILOTECA_SOURCES": "seed",
            "BAILOTECA_SEARCH_PROVIDERS": "tinyfish, brave ,,",
        }
    )

    assert config.search_providers == ["tinyfish", "brave"]


def test_config_usa_providers_por_defecto():
    config = Config.from_env({"BAILOTECA_SOURCES": "seed"})

    assert config.search_providers == ["brave", "tinyfish", "serpapi"]
