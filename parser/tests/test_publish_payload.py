import inspect

from bailoteca import publish
from bailoteca.publish import location_values, validate_payload


def test_validate_payload_accepts_bachata():
    payload = {
        "name": "Academia Bachata",
        "styles": [{"slug": "bachata", "confidence": 0.9}],
    }

    assert validate_payload(payload)["styles"][0]["slug"] == "bachata"


def test_location_values_derives_region_from_comuna():
    values = location_values({"comuna": "Santiago", "address": "Av. 1"}, "a1")

    assert values[6] == "metropolitana"


def test_location_values_unknown_comuna_has_no_region():
    values = location_values({"comuna": "Comuna Inexistente"}, "a1")

    assert values[6] is None


def test_location_values_keeps_insert_order():
    values = location_values(
        {
            "label": "Sede",
            "address": "Av. 1",
            "comuna": "Santiago",
            "lat": -33.4,
            "lng": -70.6,
            "source_url": "https://ejemplo.cl",
        },
        "a1",
    )

    assert values == (
        "a1",
        "Sede",
        "Av. 1",
        "Santiago",
        -33.4,
        -70.6,
        "metropolitana",
        "https://ejemplo.cl",
    )


def test_write_relations_insert_includes_region():
    source = inspect.getsource(publish._write_relations)

    assert "insert into academy_locations" in source
    assert "region" in source.split("insert into academy_locations", 1)[1]
