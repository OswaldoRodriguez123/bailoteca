from bailoteca_api.config import Settings
from bailoteca_api.db import get_conn
from bailoteca_api.main import create_app
from fastapi.testclient import TestClient

ACADEMY = {
    "id": "00000000-0000-0000-0000-000000000001",
    "slug": "danson-academy",
    "name": "Dansón Academy",
    "status": "active",
}


def _override_conn(client):
    client.app.dependency_overrides[get_conn] = lambda: object()


def test_list_academies_returns_page(client, monkeypatch):
    calls = {}

    def fake(conn, **kwargs):
        calls.update(kwargs)
        return [ACADEMY], 1

    monkeypatch.setattr(
        "bailoteca_api.routers.academies.query_academies", fake
    )
    _override_conn(client)

    response = client.get(
        "/academies?page=2&page_size=10"
        "&comuna=Providencia&style=salsa-cubana&q=danson"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 2
    assert body["page_size"] == 10
    assert body["total"] == 1
    assert body["items"][0]["slug"] == "danson-academy"
    assert calls == {
        "comuna": "Providencia",
        "style": "salsa-cubana",
        "q": "danson",
        "region": None,
        "limit": 10,
        "offset": 10,
        "sort": "destacadas",
        "lat": None,
        "lng": None,
    }


def test_empty_filters_are_ignored(client, monkeypatch):
    calls = {}

    def fake(conn, **kwargs):
        calls.update(kwargs)
        return [], 0

    monkeypatch.setattr(
        "bailoteca_api.routers.academies.query_academies", fake
    )
    _override_conn(client)

    response = client.get("/academies?comuna=&style=&q=")

    assert response.status_code == 200
    assert calls == {
        "comuna": None,
        "style": None,
        "q": None,
        "region": None,
        "limit": 20,
        "offset": 0,
        "sort": "destacadas",
        "lat": None,
        "lng": None,
    }


def test_q_of_one_character_returns_422(client):
    _override_conn(client)
    response = client.get("/academies?q=a")
    assert response.status_code == 422


def test_invalid_style_returns_422(client):
    _override_conn(client)
    response = client.get("/academies?style=Salsa%20Cubana")
    assert response.status_code == 422


def test_page_size_over_limit_returns_422(client):
    _override_conn(client)
    response = client.get("/academies?page_size=101")
    assert response.status_code == 422


def test_page_out_of_range_returns_empty_items(client, monkeypatch):
    monkeypatch.setattr(
        "bailoteca_api.routers.academies.query_academies",
        lambda conn, **kwargs: ([], 5),
    )
    _override_conn(client)

    response = client.get("/academies?page=99&page_size=20")

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 5


def test_missing_database_returns_503():
    app = create_app(
        Settings(
            database_url_readonly="",
            rate_limit="1000/minute",
            db_pool_max_size=2,
        )
    )
    with TestClient(app) as client:
        response = client.get("/academies")
    assert response.status_code == 503
    assert response.json() == {"detail": "Base de datos no disponible"}


def test_get_academy_by_slug(client, monkeypatch):
    monkeypatch.setattr(
        "bailoteca_api.routers.academies.get_academy_by_slug",
        lambda conn, slug: ACADEMY,
    )
    _override_conn(client)

    response = client.get("/academies/danson-academy")

    assert response.status_code == 200
    assert response.json()["slug"] == "danson-academy"


def test_get_academy_not_found(client, monkeypatch):
    monkeypatch.setattr(
        "bailoteca_api.routers.academies.get_academy_by_slug",
        lambda conn, slug: None,
    )
    _override_conn(client)

    response = client.get("/academies/no-existe")

    assert response.status_code == 404
    assert response.json() == {"detail": "Academia no encontrada"}


def test_styles(client, monkeypatch):
    monkeypatch.setattr(
        "bailoteca_api.routers.academies.query_styles",
        lambda conn: [{"slug": "mambo", "name": "Mambo", "sort": 30}],
    )
    _override_conn(client)

    response = client.get("/styles")

    assert response.status_code == 200
    assert response.json() == {
        "items": [{"slug": "mambo", "name": "Mambo", "sort": 30}]
    }


def test_comunas_defaults_to_metropolitana(client, monkeypatch):
    calls = {}

    def fake(conn, **kwargs):
        calls.update(kwargs)
        return ["Providencia"]

    monkeypatch.setattr(
        "bailoteca_api.routers.academies.query_comunas", fake
    )
    _override_conn(client)

    response = client.get("/comunas")

    assert response.status_code == 200
    assert response.json() == {"items": ["Providencia"]}
    assert calls == {"region": "metropolitana"}


def test_comunas_region_all(client, monkeypatch):
    calls = {}

    def fake(conn, **kwargs):
        calls.update(kwargs)
        return ["Providencia"]

    monkeypatch.setattr(
        "bailoteca_api.routers.academies.query_comunas", fake
    )
    _override_conn(client)

    response = client.get("/comunas?region=all")

    assert response.status_code == 200
    assert calls == {"region": "all"}


def test_comunas_unknown_region_422(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "bailoteca_api.routers.academies.query_comunas",
        lambda conn, **kwargs: calls.append(kwargs) or [],
    )
    _override_conn(client)

    response = client.get("/comunas?region=marte")

    assert response.status_code == 422
    assert calls == []


def test_list_regions_returns_16(client):
    response = client.get("/regions")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 16
    assert items[0]["slug"] == "arica"
    assert {"slug": "metropolitana", "name": "Región Metropolitana"} in items


def test_academies_passes_region(client, monkeypatch):
    calls = {}

    def fake(conn, **kwargs):
        calls.update(kwargs)
        return [ACADEMY], 1

    monkeypatch.setattr(
        "bailoteca_api.routers.academies.query_academies", fake
    )
    _override_conn(client)

    response = client.get("/academies?region=valparaiso")

    assert response.status_code == 200
    assert calls == {
        "comuna": None,
        "style": None,
        "q": None,
        "region": "valparaiso",
        "limit": 20,
        "offset": 0,
        "sort": "destacadas",
        "lat": None,
        "lng": None,
    }


def test_academies_without_region_passes_none(client, monkeypatch):
    calls = {}

    def fake(conn, **kwargs):
        calls.update(kwargs)
        return [], 0

    monkeypatch.setattr(
        "bailoteca_api.routers.academies.query_academies", fake
    )
    _override_conn(client)

    response = client.get("/academies")

    assert response.status_code == 200
    assert calls["region"] is None


def test_academies_unknown_region_422(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "bailoteca_api.routers.academies.query_academies",
        lambda conn, **kwargs: calls.append(kwargs) or ([], 0),
    )
    _override_conn(client)

    response = client.get("/academies?region=marte")

    assert response.status_code == 422
    assert calls == []



def test_sort_invalid_422(client):
    _override_conn(client)
    assert client.get("/academies?sort=precio").status_code == 422


def test_cercanas_requires_valid_coordinates(client):
    _override_conn(client)
    assert client.get("/academies?sort=cercanas").status_code == 422
    assert client.get("/academies?sort=cercanas&lat=999&lng=-70.6").status_code == 422


def test_cercanas_forwards_coordinates(client, monkeypatch):
    calls = {}
    monkeypatch.setattr(
        "bailoteca_api.routers.academies.query_academies",
        lambda conn, **kw: (calls.update(kw), ([], 0))[1],
    )
    _override_conn(client)

    response = client.get("/academies?sort=cercanas&lat=-33.45&lng=-70.66")

    assert response.status_code == 200
    assert (calls["sort"], calls["lat"], calls["lng"]) == ("cercanas", -33.45, -70.66)


def test_coordinates_are_ignored_for_other_sorts(client, monkeypatch):
    calls = {}
    monkeypatch.setattr(
        "bailoteca_api.routers.academies.query_academies",
        lambda conn, **kw: (calls.update(kw), ([], 0))[1],
    )
    _override_conn(client)

    client.get("/academies?sort=nuevas&lat=-33.45&lng=-70.66")

    assert calls["sort"] == "nuevas"
    assert calls["lat"] is None and calls["lng"] is None
