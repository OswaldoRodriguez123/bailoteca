from pathlib import Path
from unittest.mock import patch

import pytest

from bailoteca.enrich import (
    CachedFetcher,
    Page,
    enrich,
    extract_address,
    extract_description,
    extract_jsonld,
    extract_social_links,
    safe_url,
)
from bailoteca.models import Candidate

FIXTURES = Path(__file__).parent / "fixtures"
HTML = (FIXTURES / "sitio.html").read_text()


def _mock_resolve(host):
    # academia.cl -> public IP
    if host == "academia.cl":
        return ["8.8.8.8"]
    return []


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
    with patch("bailoteca.enrich._resolve_host", _mock_resolve):
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


def test_enrich_adds_candidate_social_url_as_link():
    page = Page("https://www.facebook.com/MamboRockChile/", 200, "", "")
    enriched = enrich(
        Candidate("Mambo Roakes", "https://www.facebook.com/MamboRockChile/", None, "serpapi"),
        _FakeFetcher(page),
    )
    assert enriched.links["facebook"] == ["https://facebook.com/MamboRockChile/"]


def test_cached_fetcher_only_fetches_once(tmp_path):
    fetcher = _FakeFetcher(Page("https://demo.cl", 200, HTML, "texto"))
    cached = CachedFetcher(fetcher, tmp_path)
    cached.get("https://demo.cl")
    cached.get("https://demo.cl")
    assert fetcher.calls == 1


class _FakeStreamResponse:
    def __init__(self, url, status=200, body=b"contenido"):
        self.url = url
        self.status_code = status
        self.encoding = "utf-8"
        self._body = body
        self.read = False

    def iter_bytes(self):
        self.read = True
        yield self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_redirect_to_private_target_is_not_read():
    response = _FakeStreamResponse("http://169.254.169.254/latest/meta-data")

    def fake_stream(method, url, **kwargs):
        return response

    from bailoteca.enrich import HttpxFetcher

    page = HttpxFetcher(stream_fn=fake_stream).get("https://seguro.cl")
    assert page.status == 0
    assert page.html == ""
    assert response.read is False


def test_enrich_fetches_instagram_profile_and_reads_meta():
    page_html = (FIXTURES / "instagram-profile.html").read_text()
    fetcher = _FakeFetcher(Page("https://instagram.com/salsawizards", 200, page_html, "Salsa Wizards 5,420 Followers"))
    enriched = enrich(
        Candidate(
            "Salsa Wizards", "https://www.instagram.com/salsawizards/", "salsawizards", "seed"
        ),
        fetcher,
    )
    assert fetcher.calls == 1
    assert enriched.description is not None
    assert "Academia de salsa" in enriched.description or "Salsa dancers" in enriched.description
    assert enriched.links["instagram"] == ["https://instagram.com/salsawizards"]


def test_extract_social_links_drops_facebook_nav_urls():
    from bailoteca.enrich import _normalize_social

    nav = [
        "https://www.facebook.com/about/",
        "https://www.facebook.com/help/1234",
        "https://www.facebook.com/login",
        "https://www.facebook.com/watch/?v=123",
        "https://www.facebook.com/photo.php?fbid=123",
        "https://www.facebook.com/ad_campaign/landing.php",
    ]
    for url in nav:
        assert _normalize_social("facebook", url) is None, url


def test_extract_social_links_keeps_business_profile():
    from bailoteca.enrich import _normalize_social

    assert _normalize_social("facebook", "https://www.facebook.com/MamboRockChile/") == "https://facebook.com/MamboRockChile/"
    assert _normalize_social("facebook", "https://www.facebook.com/p/Entredanzas-Academia-100092571087976/") == "https://www.facebook.com/p/Entredanzas-Academia-100092571087976/"
