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
