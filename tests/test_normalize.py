import pytest

from directorio_baile.normalize import (
    candidate_key,
    domain_of,
    normalize_handle,
    normalize_name,
    payload_hash,
    slugify,
)


def test_normalize_name_removes_accents_generic_words_and_punctuation():
    assert normalize_name("  Academia de Salsa ¡Cubana! ") == "salsa cubana"
    assert normalize_name("Escuela de Baile Ñuñoa") == "baile nunoa"


def test_slugify_handles_accents():
    assert slugify("Salsa en Línea Ñuñoa") == "salsa-en-linea-nunoa"


def test_domain_of_strips_www_and_query():
    assert domain_of("https://www.instagram.com/foo/?hl=es") == "instagram.com"
    assert domain_of("not a url") is None
    assert domain_of(None) is None


def test_normalize_handle():
    assert normalize_handle(" @Foo.Bar ") == "foo.bar"
    assert normalize_handle(None) is None


def test_candidate_key_is_stable_across_url_variants():
    a = candidate_key("Academia X", "https://academiax.cl/", None, "Providencia")
    b = candidate_key("academia x", "http://www.academiax.cl", None, None)
    assert a == b


def test_candidate_key_uses_handle_when_no_url():
    key = candidate_key("Academia X", None, "@academia.x", "Providencia")
    assert key == "x|ig:academia.x"


def test_payload_hash_ignores_dict_order():
    assert payload_hash({"a": 1, "b": 2}) == payload_hash({"b": 2, "a": 1})
    assert payload_hash({"a": 1}) != payload_hash({"a": 2})
