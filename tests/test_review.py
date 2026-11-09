from directorio_baile.propose import field_value_hash
from directorio_baile.publish import replaced_pairs
from directorio_baile.review import render_review


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
