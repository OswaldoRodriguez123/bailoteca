from bailoteca.classify import (
    classify,
    merge_hits,
    needs_review,
    rule_hits,
)
from bailoteca.llm import StyleHit


def test_salsa_as_food_is_not_a_dance_style():
    assert rule_hits("Salsa de tomate casera, la mejor del barrio") == []


def test_rules_detect_cubana_linea_and_mambo():
    assert [h.slug for h in rule_hits("Clases de salsa cubana y rueda de casino")] == [
        "salsa-cubana"
    ]
    assert [h.slug for h in rule_hits("Salsa en línea on1 y mambo")] == [
        "salsa-linea",
        "mambo",
    ]


def test_rules_detect_bachata():
    assert [h.slug for h in rule_hits("Clases de bachata los martes")] == [
        "bachata"
    ]
    assert [h.slug for h in rule_hits("Bachata sensual y dominicana")] == [
        "bachata"
    ]
    assert [h.slug for h in rule_hits("Salsa cubana y bachata moderna")] == [
        "salsa-cubana",
        "bachata",
    ]


def test_strong_rule_contradicted_by_llm_is_disputed():
    merged = merge_hits(
        [StyleHit("salsa-cubana", 0.9)],
        [StyleHit("salsa-cubana", 0.2, "salsa en linea")],
    )
    assert merged[0].disputed is True
    assert needs_review(merged[0]) is True


def test_llm_quote_must_exist_in_text():
    class FakeLLM:
        def classify_styles(self, text, slugs):
            return [StyleHit("mambo", 0.95, "no aparece")]

    assert classify("clases de baile los martes", FakeLLM()) == []


def test_llm_hit_with_valid_quote_is_kept():
    class FakeLLM:
        def classify_styles(self, text, slugs):
            return [StyleHit("mambo", 0.95, "clases de mambo")]

    hits = classify("clases de mambo los martes", FakeLLM())
    assert hits == [StyleHit("mambo", 0.95, "clases de mambo")]


def test_thresholds():
    assert needs_review(StyleHit("mambo", 0.70)) is True
    assert needs_review(StyleHit("mambo", 0.90)) is False
