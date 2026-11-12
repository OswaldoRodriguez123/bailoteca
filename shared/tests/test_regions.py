import pytest

from bailoteca_shared.regions import (
    REGIONS,
    REGION_SLUGS,
    comunas_in_region,
    normalize_comuna,
    region_slug_for_comuna,
    regions,
)


def test_regions_lists_the_sixteen_region_slugs():
    catalog = regions()
    assert len(catalog) == 16
    assert len({region["slug"] for region in catalog}) == 16
    assert {region["slug"] for region in catalog} == set(REGION_SLUGS)


def test_metropolitana_is_last_and_named():
    assert REGIONS[-1] == ("metropolitana", "Región Metropolitana")


def test_catalog_has_346_comunas():
    total = sum(len(comunas_in_region(slug)) for slug, _ in REGIONS)
    assert total == 346


def test_metropolitana_comunas():
    comunas = comunas_in_region("metropolitana")
    assert len(comunas) == 52
    for name in ("Santiago", "Ñuñoa", "Tiltil", "Estación Central"):
        assert name in comunas


def test_metropolitana_comunas_are_sorted():
    comunas = comunas_in_region("metropolitana")
    assert comunas == sorted(comunas, key=str.casefold)


@pytest.mark.parametrize(
    ("comuna", "expected"),
    [
        ("Santiago", "metropolitana"),
        ("Providencia", "metropolitana"),
        ("nunoa", "metropolitana"),
        ("ÑUÑOA", "metropolitana"),
        ("  Ñuñoa  ", "metropolitana"),
        ("Chillán", "nuble"),
        ("Concepción", "biobio"),
        ("Valparaíso", "valparaiso"),
        ("Tiltil", "metropolitana"),
        ("Los Álamos", "biobio"),
        ("Río Bueno", "los-rios"),
        ("Cochamó", "los-lagos"),
        ("O'Higgins", "aysen"),
        ("Tierra del Fuego", None),
        ("Springfield", None),
        ("", None),
        (None, None),
    ],
)
def test_region_slug_for_comuna(comuna, expected):
    assert region_slug_for_comuna(comuna) == expected


def test_roundtrip_every_catalog_comuna():
    for slug, _ in REGIONS:
        for comuna in comunas_in_region(slug):
            assert region_slug_for_comuna(comuna) == slug


def test_normalize_comuna_strips_marks_punctuation_and_spaces():
    assert normalize_comuna("  Ñuñoa  ") == "nunoa"
    assert normalize_comuna("O'Higgins") == "ohiggins"
    assert normalize_comuna("Los Álamos") == "los alamos"


@pytest.mark.parametrize("slug", ["all", "xx"])
def test_comunas_in_unknown_region_raises(slug):
    with pytest.raises(ValueError):
        comunas_in_region(slug)
