from bailoteca.places import parse_place


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