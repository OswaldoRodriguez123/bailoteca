from pathlib import Path

import pytest

from directorio_baile.enrich import (
    CachedFetcher,
    Page,
    enrich,
    extract_address,
    extract_description,
    extract_jsonld,
    extract_social_links,
    safe_url,
)
from directorio_baile.models import Candidate

FIXTURES = Path(__file__).parent / "fixtures"
HTML = (FIXTURES / "sitio.html").read_text()


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://academia.cl", True),
        ("http://academia.cl/pagina", True),
        ("file:///etc/passwd", False),
        ("javascript:alert(1)", False),
        ("http://localhost:8000", False),
        ("http://127.0.0.1", False),
        ("http://169.254.169.254/latest/meta-data", False),
        ("http://[::1]/", False),
    ],
)
def test_safe_url(url, expected):
    assert safe_url(url) is expected


def test_extract_description_from_meta():
    assert extract_description(HTML) == "Academia de salsa cubana en Providencia."


def test_extract_jsonld_and_address():
    jsonlds = extract_jsonld(HTML)
    address, comuna = extract_address(jsonlds)
    assert address == "Av. Providencia 123"
    assert comuna == "Providencia"


def test_extract_social_links_ignores_sharers():
    links = extract_social_links(HTML, "https://demo.cl")
    assert links["instagram"] == ["https://instagram.com/academia_demo"]
    assert links["email"] == ["mailto:hola@demo.cl"]
    assert links["phone"] == ["tel:+56911111111"]
    assert "facebook" not in links


def test_enrich_keeps_instagram_only_academy():
    page = Page("https://instagram.com/soloig", 200, "", "")
    enriched = enrich(
        Candidate("Solo IG", "https://instagram.com/soloig", "soloig", "seed"),
        _FakeFetcher(page),
    )
    assert enriched.links["instagram"] == ["https://instagram.com/soloig"]
    assert enriched.description is None
    assert enriched.page_url == "https://instagram.com/soloig"


class _FakeFetcher:
    def __init__(self, page):
        self.page = page
        self.calls = 0

    def get(self, url):
        self.calls += 1
        return self.page


def test_cached_fetcher_only_fetches_once(tmp_path):
    fetcher = _FakeFetcher(Page("https://demo.cl", 200, HTML, "texto"))
    cached = CachedFetcher(fetcher, tmp_path)
    cached.get("https://demo.cl")
    cached.get("https://demo.cl")
    assert fetcher.calls == 1
