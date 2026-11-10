import json

from bailoteca.dedupe import build_existing_index, is_duplicate
from bailoteca.models import Candidate


def _existing_index():
    published = [
        {
            "id": "pub1",
            "name": "Bailemos Salsa",
            "slug": "bailemos-salsa",
            "locations": [{"comuna": "Providencia"}],
            "links": [
                {"kind": "web", "url": "https://bailemosalsa.cl/"},
                {"kind": "instagram", "url": "https://instagram.com/bailemosalsa/"},
                {"kind": "facebook", "url": "https://www.facebook.com/Bailemosalsa/"},
            ],
        }
    ]
    pending = [
        {
            "name": "Academia de Baile Mushin",
            "locations": [{"comuna": "Providencia"}],
            "links": [{"kind": "web", "url": "https://misclasedebaile.cl/"}],
        }
    ]
    return build_existing_index(published, pending)


def test_filters_name_match_even_with_extra_text():
    index = _existing_index()
    cand = Candidate(
        name="Academia Bailemos Salsa | Providencia",
        url="https://bailemosalsa.cl/clases",
        handle=None,
        source="brave",
        comuna=None,
    )
    assert is_duplicate(cand, index) is True


def test_filters_published_handle_match():
    index = _existing_index()
    cand = Candidate(
        name="Clases de Salsa",
        url="https://instagram.com/bailemosalsa",
        handle="bailemosalsa",
        source="brave",
    )
    assert is_duplicate(cand, index) is True


def test_filters_facebook_handle_match():
    index = _existing_index()
    cand = Candidate(
        name="Bailemos Salsa Chile",
        url="https://www.facebook.com/Bailemosalsa",
        handle=None,
        source="brave",
    )
    assert is_duplicate(cand, index) is True


def test_filters_same_website_domain():
    index = _existing_index()
    cand = Candidate(
        name="Academia Bailemos Salsa",
        url="https://www.bailemosalsa.cl/contacto",
        handle=None,
        source="brave",
    )
    assert is_duplicate(cand, index) is True


def test_filters_pending_proposal_by_url():
    index = _existing_index()
    cand = Candidate(
        name="Academia de Baile Mushin Providencia | Salsa",
        url="https://www.misclasedebaile.cl/horarios/",
        handle=None,
        source="brave",
    )
    assert is_duplicate(cand, index) is True


def test_keeps_new_academy():
    index = _existing_index()
    cand = Candidate(
        name="Candela Dance Studio",
        url="https://candeladance.cl/",
        handle=None,
        source="brave",
    )
    assert is_duplicate(cand, index) is False


def test_filters_exact_canonical_url():
    index = _existing_index()
    cand = Candidate(
        name="Totally Different Name",
        url="https://misclasedebaile.cl/",
        handle=None,
        source="brave",
    )
    assert is_duplicate(cand, index) is True


def test_keeps_subdomain_and_other_domain():
    index = _existing_index()
    cand = Candidate(
        name="Candela Dance Studio",
        url="https://www.candeladance.cl/",
        handle=None,
        source="brave",
    )
    assert is_duplicate(cand, index) is False
