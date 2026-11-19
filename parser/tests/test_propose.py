from bailoteca.enrich import Enriched
from bailoteca.llm import StyleHit
from bailoteca.models import Candidate
from bailoteca.propose import build_proposal, field_value_hash, style_payload


def _enriched(**overrides):
    base = dict(
        candidate=Candidate("Academia X", "https://x.cl", None, "seed"),
        page_url="https://x.cl",
        text="Clases de salsa cubana",
        address="Av. X 1",
        comuna="Providencia",
        links={"instagram": ["https://instagram.com/x"]},
        description="Academia de salsa cubana.",
        evidence={},
    )
    base.update(overrides)
    return Enriched(**base)


def test_low_confidence_style_is_dropped():
    payload = style_payload([StyleHit("salsa-cubana", 0.9), StyleHit("mambo", 0.5)])
    assert payload == [{"slug": "salsa-cubana", "confidence": 0.9, "evidence": None}]


def test_build_proposal_for_new_academy_marks_review():
    draft = build_proposal(
        _enriched().candidate,
        _enriched(),
        [StyleHit("salsa-cubana", 0.9)],
        existing=None,
        rejections=set(),
    )
    assert draft.kind == "create"
    assert draft.needs_review is False
    assert draft.payload["styles"][0]["slug"] == "salsa-cubana"


def test_unchanged_existing_academy_proposes_nothing():
    existing = {
        "name": "Academia X",
        "description": "Academia de salsa cubana.",
        "address": "Av. X 1",
        "comuna": "Providencia",
        "instagram": "https://instagram.com/x",
        "styles": [{"slug": "salsa-cubana", "confidence": 0.9}],
    }
    draft = build_proposal(
        _enriched().candidate,
        _enriched(),
        [StyleHit("salsa-cubana", 0.9)],
        existing=existing,
        rejections=set(),
    )
    assert draft is None


def test_rejected_field_is_not_proposed_again():
    bad = field_value_hash("address", "Av. X 1")
    draft = build_proposal(
        _enriched().candidate,
        _enriched(),
        [StyleHit("salsa-cubana", 0.9)],
        existing=None,
        rejections={("address", bad)},
    )
    assert "address" not in draft.payload["locations"][0]


def test_disputed_style_needs_review():
    draft = build_proposal(
        _enriched().candidate,
        _enriched(),
        [StyleHit("salsa-cubana", 0.9, disputed=True)],
        existing=None,
        rejections=set(),
    )
    assert draft.needs_review is True


def test_rejected_address_on_update_keeps_existing_value():
    existing = {
        "name": "Academia X",
        "description": "Vieja",
        "address": "Av. X 1",
        "comuna": "Providencia",
        "instagram": "https://instagram.com/x",
        "styles": [{"slug": "salsa-cubana"}],
    }
    bad = field_value_hash("address", "Av. X 1")
    draft = build_proposal(
        _enriched(description="Nueva").candidate,
        _enriched(description="Nueva"),
        [StyleHit("salsa-cubana", 0.9)],
        existing=existing,
        rejections={("address", bad)},
    )
    assert draft.payload["locations"][0]["address"] == "Av. X 1"


def test_existing_with_list_published_shape_keeps_fallback_values():
    """list_published devuelve locations/links/styles, no campos planos."""
    existing = {
        "id": "aaaaaaaa-0000-0000-0000-000000000001",
        "name": "Academia X",
        "description": "Academia de salsa cubana.",
        "locations": [
            {
                "label": None,
                "address": "Av. X 1",
                "comuna": "Providencia",
                "lat": None,
                "lng": None,
                "source_url": None,
            }
        ],
        "links": [{"kind": "instagram", "url": "https://instagram.com/x"}],
        "styles": [
            {
                "slug": "salsa-cubana",
                "name": "Salsa cubana",
                "confidence": 0.9,
                "evidence": None,
            }
        ],
        "verified_at": None,
    }
    # Sin cambios reales: no debe proponer nada
    draft = build_proposal(
        _enriched().candidate,
        _enriched(),
        [StyleHit("salsa-cubana", 0.9)],
        existing=existing,
        rejections=set(),
    )
    assert draft is None

    # Con cambio de descripción y sin dirección nueva: el fallback debe
    # conservar dirección/comuna/estilos de la ficha publicada
    draft = build_proposal(
        _enriched(description="Nueva", address=None, comuna=None, links={}).candidate,
        _enriched(description="Nueva", address=None, comuna=None, links={}),
        [],
        existing=existing,
        rejections=set(),
    )
    assert draft is not None
    assert draft.kind == "update"
    assert draft.payload["locations"][0]["address"] == "Av. X 1"
    assert draft.payload["locations"][0]["comuna"] == "Providencia"
    assert draft.payload["links"] == [{"kind": "instagram", "url": "https://instagram.com/x"}]
    # Los estilos copiados no deben arrastrar 'name' (validación extra=forbid)
    assert draft.payload["styles"] == [{"slug": "salsa-cubana", "confidence": 0.9, "evidence": None}]


def test_build_proposal_falls_back_to_candidate_description_when_enriched_has_none():
    candidate = Candidate(
        "Academia X",
        "https://x.cl",
        None,
        "brave",
        raw={"description": "Clases de salsa desde cero."},
    )
    draft = build_proposal(
        candidate,
        _enriched(description=None, page_url="https://x.cl"),
        [StyleHit("salsa-cubana", 0.9)],
        existing=None,
        rejections=set(),
    )
    assert draft.payload["description"] == "Clases de salsa desde cero."


def test_build_proposal_prefers_enriched_description_over_candidate_description():
    candidate = Candidate(
        "Academia X",
        "https://x.cl",
        None,
        "brave",
        raw={"description": "Snippet de búsqueda."},
    )
    draft = build_proposal(
        candidate,
        _enriched(description="Descripción real de la página."),
        [StyleHit("salsa-cubana", 0.9)],
        existing=None,
        rejections=set(),
    )
    assert draft.payload["description"] == "Descripción real de la página."


def test_llm_noise_omits_description_for_new_academy():
    enriched = _enriched(description=None, suppress_description=True)
    draft = build_proposal(
        enriched.candidate,
        enriched,
        [StyleHit("salsa-cubana", 0.9)],
        existing=None,
        rejections=set(),
    )
    assert "description" not in draft.payload


def test_llm_noise_keeps_existing_published_description():
    enriched = _enriched(description=None, suppress_description=True)
    existing = {
        "id": "acad-1",
        "name": "Academia X",
        "description": "Descripción publicada y revisada.",
        "locations": [],
        "styles": [],
    }
    draft = build_proposal(
        enriched.candidate,
        enriched,
        [StyleHit("salsa-cubana", 0.9)],
        existing=existing,
        rejections=set(),
    )
    assert draft.payload["description"] == "Descripción publicada y revisada."


def test_update_payload_union_links():
    """El `update` conserva los links publicados que el enrich no detectó."""
    existing = {
        "name": "Academia X",
        "description": "Vieja descripción",
        "address": "Av. X 1",
        "comuna": "Providencia",
        "links": [
            {"kind": "instagram", "url": "https://instagram.com/x"},
            {"kind": "whatsapp", "url": "https://wa.me/56965387513"},
        ],
        "styles": [{"slug": "salsa-cubana", "confidence": 0.9}],
    }
    # Hay cambio de descripción (fuerza la propuesta) → el payload debe unir links
    draft = build_proposal(
        _enriched().candidate,  # enrich solo detecta instagram
        _enriched(),
        [StyleHit("salsa-cubana", 0.9)],
        existing=existing,
        rejections=set(),
    )
    assert draft is not None
    assert "description" in draft.changes
    payload_links = {(l["kind"], l["url"]) for l in draft.payload["links"]}
    assert payload_links == {
        ("instagram", "https://instagram.com/x"),
        ("whatsapp", "https://wa.me/56965387513"),
    }


def test_update_payload_union_links_respects_rejection():
    """Un link publicado pero rechazado explícitamente no resucita."""
    url = "https://wa.me/56965387513"
    existing = {
        "name": "Academia X",
        "description": "Academia de salsa cubana.",
        "address": "Av. X 1",
        "comuna": "Providencia",
        "links": [
            {"kind": "instagram", "url": "https://instagram.com/x"},
            {"kind": "whatsapp", "url": url},
        ],
        "styles": [{"slug": "salsa-cubana", "confidence": 0.9}],
    }
    bad = field_value_hash("whatsapp", url)
    draft = build_proposal(
        _enriched().candidate,
        _enriched(),
        [StyleHit("salsa-cubana", 0.9)],
        existing=existing,
        rejections={("whatsapp", bad)},
    )
    assert draft is not None
    payload_links = {(l["kind"], l["url"]) for l in draft.payload["links"]}
    assert payload_links == {("instagram", "https://instagram.com/x")}


def test_update_payload_union_styles():
    """Subset de estilos detectados se une con los publicados, respetando rechazos."""
    existing = {
        "name": "Academia X",
        "description": "Vieja descripción",  # fuerza una diferencia real
        "address": "Av. X 1",
        "comuna": "Providencia",
        "links": [{"kind": "instagram", "url": "https://instagram.com/x"}],
        "styles": [
            {"slug": "salsa-cubana", "confidence": 0.9},
            {"slug": "mambo", "confidence": 0.8, "evidence": "cita"},
        ],
    }
    # Detectado solo salsa-cubana → mambo debe conservarse
    draft = build_proposal(
        _enriched().candidate,
        _enriched(),
        [StyleHit("salsa-cubana", 0.9)],
        existing=existing,
        rejections=set(),
    )
    assert draft is not None
    assert "description" in draft.changes
    assert {s["slug"] for s in draft.payload["styles"]} == {"salsa-cubana", "mambo"}

    # Mambo publicado pero rechazado → no resucita
    bad = field_value_hash("style:mambo", "mambo")
    draft = build_proposal(
        _enriched().candidate,
        _enriched(),
        [StyleHit("salsa-cubana", 0.9)],
        existing=existing,
        rejections={("style:mambo", bad)},
    )
    assert draft is not None
    assert {s["slug"] for s in draft.payload["styles"]} == {"salsa-cubana"}


def test_update_with_subset_of_published_links_produces_no_changes():
    """Un refresh que detecta menos que lo publicado ya no genera propuesta dañina."""
    existing = {
        "name": "Academia X",
        "description": "Academia de salsa cubana.",
        "address": "Av. X 1",
        "comuna": "Providencia",
        "links": [
            {"kind": "instagram", "url": "https://instagram.com/x"},
            {"kind": "whatsapp", "url": "https://wa.me/56965387513"},
        ],
        "styles": [{"slug": "salsa-cubana", "confidence": 0.9}],
    }
    draft = build_proposal(
        _enriched().candidate,  # instagram-only + salsa-cubana: ⊂ publicado
        _enriched(),
        [StyleHit("salsa-cubana", 0.9)],
        existing=existing,
        rejections=set(),
    )
    assert draft is None


def test_create_payload_unaffected_by_union():
    """En create (existing=None) no hay unión: payload solo con lo detectado."""
    draft = build_proposal(
        _enriched().candidate,
        _enriched(),
        [StyleHit("salsa-cubana", 0.9)],
        existing=None,
        rejections=set(),
    )
    assert draft is not None
    assert draft.payload["links"] == [
        {"kind": "instagram", "url": "https://instagram.com/x"}
    ]
