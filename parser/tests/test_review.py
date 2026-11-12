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
