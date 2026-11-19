from bailoteca.propose import field_value_hash
from bailoteca.publish import replaced_pairs
from bailoteca.review import render_review


def test_render_review_flags_doubtful_and_shows_evidence():
    text = render_review(
        [
            {
                "id": "p1",
                "confidence": 0.7,
                "payload": {
                    "name": "Academia X",
                    "styles": [{"slug": "mambo", "confidence": 0.7}],
                },
                "evidence": {
                    "name": {"source_url": "https://x.cl", "confidence": 0.9}
                },
            }
        ]
    )
    assert "Academia X" in text
    assert "DUDOSO" in text
    assert "https://x.cl" in text
    assert "p1" in text


def test_replaced_pairs_reports_only_changed_fields():
    proposed = {"name": "A", "address": "X", "styles": [{"slug": "mambo"}]}
    approved = {"name": "A", "address": "Y", "styles": [{"slug": "mambo"}]}
    assert replaced_pairs(proposed, approved) == [
        ("address", field_value_hash("address", "X"))
    ]


def test_render_review_without_verdicts_renders_no_country_line():
    text = render_review(
        [
            {
                "id": "p1",
                "confidence": 0.9,
                "payload": {"name": "Academia X", "styles": []},
                "evidence": {},
            }
        ]
    )
    assert "país" not in text


def test_render_review_with_verdict_chile_renders_line_after_evidence():
    from bailoteca.country import CountryVerdict

    verdicts = {
        "p1": CountryVerdict("chile", (".cl en URL", "comuna chilena: providencia")),
    }
    text = render_review(
        [
            {
                "id": "p1",
                "confidence": 0.9,
                "payload": {"name": "Academia X", "styles": []},
                "evidence": {
                    "name": {"source_url": "https://x.cl", "confidence": 0.9}
                },
            }
        ],
        verdicts=verdicts,
    )
    assert "- país: 🇨🇱 Chile probable — señales: .cl en URL, comuna chilena: providencia" in text
    assert text.index("- evidencia:") < text.index("- país:")


def test_render_review_with_verdict_extranjera_and_sin_huella():
    from bailoteca.country import CountryVerdict

    proposals = [
        {
            "id": "p1",
            "confidence": 0.9,
            "payload": {"name": "A", "styles": []},
            "evidence": {},
        },
        {
            "id": "p2",
            "confidence": 0.9,
            "payload": {"name": "B", "styles": []},
            "evidence": {},
        },
    ]
    verdicts = {
        "p1": CountryVerdict("extranjera", ("país en dirección: españa",)),
        "p2": CountryVerdict("sin_huella", ("sin señales claras",)),
    }
    text = render_review(proposals, verdicts=verdicts)
    assert "- país: ⚠️ no parece Chile — señales: país en dirección: españa" in text
    assert "- país: ⚪ sin huella — señales: sin señales claras" in text


def test_render_review_verdict_unknown_id_is_ignored():
    from bailoteca.country import CountryVerdict

    text = render_review(
        [
            {
                "id": "p1",
                "confidence": 0.9,
                "payload": {"name": "A", "styles": []},
                "evidence": {},
            }
        ],
        verdicts={"otro": CountryVerdict("chile", ("sitio .cl",))},
    )
    assert "país" not in text


def test_replaced_pairs_records_dropped_duplicate_kind_link_only():
    proposed = {
        "links": [
            {"kind": "instagram", "url": "https://instagram.com/a"},
            {"kind": "instagram", "url": "https://instagram.com/b"},
        ]
    }
    approved = {"links": [{"kind": "instagram", "url": "https://instagram.com/b"}]}
    assert replaced_pairs(proposed, approved) == [
        ("instagram", field_value_hash("instagram", "https://instagram.com/a"))
    ]


def test_replaced_pairs_records_replaced_link_not_kept():
    proposed = {"links": [{"kind": "web", "url": "https://old.example.com"}]}
    approved = {"links": [{"kind": "web", "url": "https://new.example.com"}]}
    assert replaced_pairs(proposed, approved) == [
        ("web", field_value_hash("web", "https://old.example.com"))
    ]


def test_replaced_pairs_no_links_nothing_recorded():
    assert replaced_pairs({"links": []}, {"links": []}) == []
    assert replaced_pairs({}, {}) == []


def test_replaced_pairs_duplicate_identical_links_absent_from_approved_recorded_once():
    proposed = {
        "links": [
            {"kind": "instagram", "url": "https://instagram.com/a"},
            {"kind": "instagram", "url": "https://instagram.com/a"},
        ]
    }
    approved = {"links": []}
    assert replaced_pairs(proposed, approved) == [
        ("instagram", field_value_hash("instagram", "https://instagram.com/a"))
    ]


def test_replaced_pairs_single_dropped_sede_records_address_and_comuna():
    proposed = {
        "locations": [{"address": "Av. X 100", "comuna": "Santiago"}],
    }
    approved = {"locations": []}
    assert replaced_pairs(proposed, approved) == [
        ("address", field_value_hash("address", "Av. X 100")),
        ("comuna", field_value_hash("comuna", "Santiago")),
    ]


def test_replaced_pairs_dropped_extra_sede_records_address_but_not_shared_comuna():
    proposed = {
        "locations": [
            {"address": "Av. Keep 1", "comuna": "Santiago"},
            {"address": "Av. Drop 2", "comuna": "Santiago"},
        ]
    }
    approved = {
        "locations": [{"address": "Av. Keep 1", "comuna": "Santiago"}],
    }
    assert replaced_pairs(proposed, approved) == [
        ("address", field_value_hash("address", "Av. Drop 2"))
    ]


def test_replaced_pairs_styles_unchanged_behavior():
    proposed = {"styles": [{"slug": "mambo"}, {"slug": "salsa-cubana"}]}
    approved = {"styles": [{"slug": "mambo"}]}
    assert replaced_pairs(proposed, approved) == [
        ("style:salsa-cubana", field_value_hash("style:salsa-cubana", "salsa-cubana"))
    ]
