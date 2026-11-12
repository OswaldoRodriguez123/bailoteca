"""Tests para el triage de país (bailoteca.country)."""

from __future__ import annotations

import httpx
import pytest

from bailoteca.country import (
    AcademySnapshot,
    CountryVerdict,
    assess,
    classify_overpass_hits,
    local_points,
    sanitize_osm_name,
)


def snap(
    name: str = "Bailemos",
    urls: tuple[str, ...] = (),
    phones: tuple[str, ...] = (),
    address_texts: tuple[str, ...] = (),
    comuna: str | None = None,
) -> AcademySnapshot:
    return AcademySnapshot(
        name=name, urls=urls, phones=phones, address_texts=address_texts, comuna=comuna
    )


# ---------------------------------------------------------------- C signals

def test_chile_signals_sum():
    points, reasons = local_points(
        snap(
            urls=("https://bailemos.cl/",),
            phones=("tel:+56223456789",),
            address_texts=(),
            comuna="Providencia",
        )
    )
    assert points == 3
    assert ".cl" in " ".join(reasons)
    assert any("+56" in r for r in reasons)
    assert any("providencia" in r.lower() for r in reasons)


def test_tel_international_negative():
    points, reasons = local_points(snap(phones=("tel:+17135551234",)))
    assert points == -2
    assert any("teléfono internacional: +1713" in r for r in reasons)


def test_tel_foreign_international_without_plus():
    points, _ = local_points(snap(phones=("17135551234",)))
    assert points == -2


def test_cl_phone_without_tel_prefix():
    points, reasons = local_points(snap(phones=("+56912345678",)))
    assert points == 1
    assert any("+56" in r for r in reasons)


def test_phone_garbage_ignored():
    points, reasons = local_points(snap(phones=("", "abc", "56 ")))
    assert points == 0


def test_foreign_country_token_in_address_negative():
    points, reasons = local_points(
        snap(address_texts=("Calle Algar 20, 46688 Polinyà de Xúquer, Valencia, España",))
    )
    assert points == -2
    assert any("españa" in r for r in reasons)


def test_foreign_token_argentina():
    points, reasons = local_points(snap(address_texts=("Sarmiento 1729, Argentina",)))
    assert points == -2
    assert any("argentina" in r for r in reasons)


def test_description_is_not_a_country_signal():
    # «danza española» / flamenco no entran: la descripción no viaja en address_texts.
    points, reasons = local_points(snap(address_texts=("Av. Irarrázaval 1951",)))
    assert points == 0


def test_comuna_unknown_no_point():
    points, _ = local_points(snap(comuna="Atlantis"))
    assert points == 0


def test_comuna_catalog_case_insensitive():
    points, reasons = local_points(snap(comuna="san miguel"))
    assert points == 1


# ------------------------------------------------------------- verdict local

def test_local_chile_threshold():
    v = assess(snap(urls=("https://x.cl/",), comuna="Providencia"), skip_osm=True)
    assert v.verdict == "chile"


def test_local_extranjera_threshold():
    v = assess(snap(address_texts=("Calle Algar 20, Valencia, España",)), skip_osm=True)
    assert v.verdict == "extranjera"


def test_local_strong_foreign_without_contrast_wins():
    v = assess(snap(address_texts=("Maipu 123, Argentina",)), skip_osm=True)
    assert v.verdict == "extranjera"


def test_local_contradiction_falls_to_sin_huella():
    v = assess(
        snap(urls=("https://x.cl/",), address_texts=("Maipu 123, Argentina",)),
        skip_osm=True,
    )
    assert v.verdict == "sin_huella"


def test_local_neutral_sin_huella():
    v = assess(snap(name="Bailemos"), skip_osm=True)
    assert v.verdict == "sin_huella"
    assert "sin señales claras" in " ".join(v.reasons)


def test_chilean_phone_blocks_local_extranjera():
    v = assess(
        snap(phones=("tel:+56912345678",), address_texts=("Calle Algar 20, Valencia, España",)),
        skip_osm=True,
    )
    assert v.verdict == "sin_huella"


# ------------------------------------------------------- OSM / overpass bits

def test_sanitize_osm_name():
    assert sanitize_osm_name('Rock & Roller "VIP"') == "Rock & Roller VIP"
    assert sanitize_osm_name('Back\\slash "quoted"') == "Backslash quoted"
    assert sanitize_osm_name('Mezclada \\"zz\\"') == "Mezclada zz"


def test_sanitize_collapses_spaces():
    assert sanitize_osm_name("A   B  C") == "A B C"


def test_classify_addr_country_cl():
    hits = [{"tags": {"addr:country": "CL"}}]
    assert classify_overpass_hits(hits) == (1, 0)


def test_classify_addr_country_argentina():
    hits = [{"tags": {"addr:country": "AR"}}]
    assert classify_overpass_hits(hits) == (0, 1)


def test_classify_no_country_by_coords():
    hits = [{"center": {"lat": -33.45, "lon": -70.65}}, {"center": {"lat": -34.6, "lon": -58.38}}]
    assert classify_overpass_hits(hits) == (1, 1)


def test_classify_ambiguous_hit_ignored():
    hits = [{"tags": {}}, {}]
    assert classify_overpass_hits(hits) == (0, 0)


def test_assess_osm_foreign_only():
    hits = [{"type": "node", "id": 1, "tags": {"addr:country": "AR"}}]

    class _Resp:
        def raise_for_status(self): ...
        def json(self):
            return {"elements": hits}

    class _Client:
        def post(self, url, content=None):
            return _Resp()

    v = assess(snap(name="Ritmo Candela"), client=_Client())
    assert v.verdict == "extranjera"
    assert "OSM" in " ".join(v.reasons) or "osm" in " ".join(v.reasons).lower()


def test_assess_osm_chile_only():
    hits = [{"type": "node", "id": 1, "tags": {"addr:country": "CL"}}]

    class _Resp:
        def raise_for_status(self): ...
        def json(self):
            return {"elements": hits}

    class _Client:
        def post(self, url, content=None):
            return _Resp()

    v = assess(snap(name="Ritmo Candela"), client=_Client())
    assert v.verdict == "chile"


def test_assess_osm_mixed_local_wins():
    hits = [
        {"type": "node", "id": 1, "tags": {"addr:country": "CL"}},
        {"type": "node", "id": 2, "tags": {"addr:country": "AR"}},
    ]

    class _Resp:
        def raise_for_status(self): ...
        def json(self):
            return {"elements": hits}

    class _Client:
        def post(self, url, content=None):
            return _Resp()

    v = assess(snap(name="Ritmo Candela", urls=("https://x.cl/",), comuna="Providencia"), client=_Client())
    assert v.verdict == "chile"


def test_assess_osm_failure_falls_back_local():
    class _Boom:
        def post(self, url, content=None):
            raise httpx.TimeoutException("boom")

    v = assess(snap(name="Bailemos", urls=("https://x.cl/",), comuna="Providencia"), client=_Boom())
    assert v.verdict == "chile"
    assert any("OSM sin respuesta" in r for r in v.reasons)


def test_assess_osm_skip_no_network():
    class _Boom:
        def post(self, url, content=None):
            raise AssertionError("no network expected")

    assert assess(snap(name="Bailemos"), skip_osm=True, client=_Boom()).verdict == "sin_huella"


def test_mailto_cl_is_not_a_cl_signal():
    points, _ = local_points(snap(urls=("mailto:contacto@academiax.cl",)))
    assert points == 0


def test_tel_url_does_not_count_as_cl_signal():
    # tel: en urls no suma .cl (los builders ponen los tel: en phones, que es de donde se lee +56).
    points, _ = local_points(snap(urls=("tel:+56229876543",)))
    assert points == 0
