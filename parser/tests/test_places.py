from bailoteca.places import parse_place, parse_place_google


SAMPLE = {
    "local_results": [
        {
            "title": "Bachata Sun",
            "place_id": "ChIJabc",
            "address": "Primera Transversal 3045, Maipú, Chile",
            "rating": 4.7,
            "reviews": 120,
            "price": "$$",
            "operating_hours": {"monday": "6 PM-10 PM", "tuesday": "6 PM-10 PM"},
            "open_state": "Open now",
        },
        {"title": "Otro lugar", "address": "Santiago, Chile"},
    ]
}


GOOGLE_SAMPLE = {
    "places": [
        {
            "id": "ChIJxyz",
            "displayName": {"text": "Bachata Sun", "languageCode": "es"},
            "formattedAddress": "Primera Transversal 3045, Maipú, Chile",
            "rating": 4.7,
            "userRatingCount": 120,
            "priceLevel": "PRICE_LEVEL_MODERATE",
            "regularOpeningHours": {
                "openNow": True,
                "weekdayDescriptions": [
                    "Monday: 6:00 – 10:00 PM",
                    "Tuesday: 6:00 – 10:00 PM",
                ],
            },
            "googleMapsUri": "https://maps.google.com/?cid=123",
            "internationalPhoneNumber": "+56 9 1234 5678",
            "websiteUri": "https://bachatasun.cl",
            "primaryType": "dance_school",
            "location": {"latitude": -33.5, "longitude": -70.7},
        },
        {"displayName": {"text": "Otro lugar"}, "formattedAddress": "Santiago, Chile"},
    ]
}


def test_parse_place_picks_matching_result():
    info = parse_place(SAMPLE, "Bachata Sun", "Maipú")
    assert info is not None
    assert info.place_id == "ChIJabc"
    assert info.rating == 4.7
    assert info.reviews == 120
    assert info.price == "$$"
    assert info.hours == {"monday": "6 PM-10 PM", "tuesday": "6 PM-10 PM"}
    assert info.maps_url == "https://www.google.com/maps/place/?q=place_id:ChIJabc"


def test_parse_place_returns_none_without_results():
    assert parse_place({"local_results": []}, "X", None) is None
    assert parse_place({}, "X", None) is None


def test_parse_place_google_picks_matching_result():
    info = parse_place_google(GOOGLE_SAMPLE, "Bachata Sun", "Maipú")
    assert info is not None
    assert info.place_id == "ChIJxyz"
    assert info.name == "Bachata Sun"
    assert info.rating == 4.7
    assert info.reviews == 120
    assert info.price == "$$"
    assert info.hours == {"monday": "6:00 – 10:00 PM", "tuesday": "6:00 – 10:00 PM"}
    assert info.phone == "+56 9 1234 5678"
    assert info.website == "https://bachatasun.cl"
    assert info.place_type == "dance_school"
    assert info.maps_url == "https://maps.google.com/?cid=123"
    assert info.gps_coordinates == {"latitude": -33.5, "longitude": -70.7}
    assert info.open_state == "Open now"


def test_parse_place_google_returns_none_without_results():
    assert parse_place_google({"places": []}, "X", None) is None
    assert parse_place_google({}, "X", None) is None


def test_fetch_place_google_requests_spanish():
    from bailoteca.places import fetch_place_google

    class FakeResponse:
        status_code = 200

        def json(self):
            return GOOGLE_SAMPLE

    class FakeHttp:
        def __init__(self):
            self.bodies = []

        def post(self, url, headers=None, json=None, timeout=None):
            self.bodies.append(json)
            return FakeResponse()

    http = FakeHttp()
    fetch_place_google("Bachata Sun", "Maipú", None, None, None, http, "key")

    assert http.bodies[0]["languageCode"] == "es"


def test_parse_place_google_keeps_spanish_weekday_descriptions():
    data = {
        "places": [
            {
                "id": "ChIJxyz",
                "displayName": {"text": "Bachata Sun", "languageCode": "es"},
                "formattedAddress": "Primera Transversal 3045, Maipú, Chile",
                "regularOpeningHours": {
                    "weekdayDescriptions": [
                        "lunes: 9:00–19:00",
                        "martes: Cerrado",
                    ],
                },
            }
        ]
    }

    info = parse_place_google(data, "Bachata Sun", "Maipú")

    assert info is not None
    assert info.hours == {"lunes": "9:00–19:00", "martes": "Cerrado"}
