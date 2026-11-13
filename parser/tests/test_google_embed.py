from pathlib import Path

import pytest

from bailoteca.google_embed import house_number, parse_embed_html

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_place_payload():
    r = parse_embed_html((FIXTURES / "embed_place.html").read_text())
    assert (r.lat, r.lng) == pytest.approx((-33.505288, -70.6552202))
    assert r.place_id == "ChIJ5w26K4_bYpYRpP60rsC7qSc"
    assert r.category == "dance_school"
    assert "5608" in r.resolved_address


def test_parse_address_payload():
    r = parse_embed_html((FIXTURES / "embed_address.html").read_text())
    assert (round(r.lat, 6), round(r.lng, 6)) == (-33.521305, -70.660112)
    assert r.place_id == "ChIJaxuz5eTaYpYR6ibca5rCsGI" and r.category == "subpremise"
    assert "Lucerna 064" in r.resolved_address


def test_parse_returns_none_without_init_embed():
    assert parse_embed_html("<html><body>nope</body></html>") is None


def test_parse_returns_none_on_truncated_payload():
    assert parse_embed_html("initEmbed([[null,null,") is None


def test_house_number_extracts_first_digit_token():
    assert house_number("Gran Avenida 5608, San Miguel") == "5608"
    assert house_number("Lucerna 64, La Cisterna") == "64"
    assert house_number("Séptima Avenida 1114-B") == "1114"
    assert house_number("Plaza de Maipú, Maipú") is None


from bailoteca.google_embed import EmbedResult, gate


def _r(addr, lat=-33.52, lng=-70.66):
    return EmbedResult(lat=lat, lng=lng, resolved_address=addr, place_id=None, category="subpremise")


def test_gate_accepts_leading_zero_address():
    assert gate("Lucerna 64, La Cisterna", _r("Lucerna 064, 7970329 La Cisterna, Región Metropolitana, Chile")) is None


def test_gate_rejects_number_mismatch():
    assert gate("Lucerna 64, La Cisterna", _r("Gran Av. José Miguel Carrera 8585, 7970672 La Cisterna, Región Metropolitana, Chile")) == "número no coincide"


def test_gate_matches_hyphenated_number():
    assert gate("Séptima Avenida 1114-B, San Miguel", _r("Séptima Avenida 1114-B, 8920464 San Miguel, Región Metropolitana, Chile")) is None


def test_gate_ignores_minor_digits():
    assert gate("Gran Avenida 5608, San Miguel", _r("JSD Academy - Gran Av. José Miguel Carrera 5608, Piso 2, 8930169 San Miguel, Región Metropolitana, Chile")) is None


def test_gate_requires_chile():
    assert gate("Lucerna 64, La Cisterna", _r("Lucerna 064, 7970329 La Cisterna, Región Metropolitana")) == "resolución fuera de Chile"


def test_gate_rejects_pin_outside_chile_bbox():
    assert gate("Lucerna 64, La Cisterna", _r("Lucerna 064, 7970329 La Cisterna, Chile", lat=40.0, lng=-3.0)) == "pin fuera de Chile continental"


def test_gate_requires_house_number():
    assert gate("Plaza de Maipú, Maipú", _r("Plaza de Maipú, Maipú, Región Metropolitana, Chile")) == "sin número en la dirección"
