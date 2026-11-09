from bailoteca_shared.schema import Academy


def test_academy_accepts_list_published_shape():
    academy = Academy.model_validate(
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "slug": "danson-academy",
            "name": "Dansón Academy",
            "description": "Salsa cubana.",
            "status": "unknown",
            "source_urls": [],
            "created_at": "2026-11-09T00:00:00Z",
            "updated_at": "2026-11-09T00:00:00Z",
            "verified_at": "2026-11-09T00:00:00Z",
            "locations": [
                {
                    "label": "Santiago",
                    "address": None,
                    "comuna": "Santiago",
                    "lat": None,
                    "lng": None,
                    "source_url": None,
                }
            ],
            "links": [{"kind": "web", "url": "https://danson.cl"}],
            "styles": [
                {
                    "slug": "salsa-cubana",
                    "name": "Salsa cubana",
                    "confidence": 0.9,
                    "evidence": "casino",
                }
            ],
        }
    )
    assert academy.slug == "danson-academy"
    assert academy.locations[0].comuna == "Santiago"
