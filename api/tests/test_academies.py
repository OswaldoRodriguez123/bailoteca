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
        "limit": 10,
        "offset": 10,
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
        "limit": 20,
        "offset": 0,
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
