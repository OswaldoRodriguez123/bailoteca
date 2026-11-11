from bailoteca_shared.schema import Academy, GooglePlace


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


def test_academy_accepts_cover_url_and_omits_it_when_absent():
    payload = {
        "id": "00000000-0000-0000-0000-000000000001",
        "slug": "cover-test",
        "name": "Cover Test",
        "status": "published",
        "cover_url": "https://proj.supabase.co/storage/v1/object/public/academy-covers/cover-test.jpg",
    }

    academy = Academy.model_validate(payload)
    without_cover = Academy.model_validate({k: v for k, v in payload.items() if k != "cover_url"})

    assert academy.cover_url == payload["cover_url"]
    assert without_cover.cover_url is None


def test_google_place_output_omits_thumbnail_keys():
    place = GooglePlace.model_validate(
        {
            "place_id": "place-1",
            "thumbnail": "https://lh3.googleusercontent.com/x",
            "thumbnail_source": "google",
            "thumbnail_fetched_at": "2026-11-11T00:00:00Z",
        }
    )

    dumped = place.model_dump()

    assert "thumbnail" not in dumped
    assert "thumbnail_source" not in dumped
    assert "thumbnail_fetched_at" not in dumped
