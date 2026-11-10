from bailoteca.publish import validate_payload


def test_validate_payload_accepts_bachata():
    payload = {
        "name": "Academia Bachata",
        "styles": [{"slug": "bachata", "confidence": 0.9}],
    }

    assert validate_payload(payload)["styles"][0]["slug"] == "bachata"
