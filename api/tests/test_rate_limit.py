from fastapi.testclient import TestClient
from starlette.requests import Request

from bailoteca_api.config import Settings
from bailoteca_api.db import get_conn
from bailoteca_api.main import create_app
from bailoteca_api.rate_limit import client_ip


def test_client_ip_prefers_first_forwarded_for():
    request = Request(
        {
            "type": "http",
            "headers": [(b"x-forwarded-for", b"1.2.3.4, 5.6.7.8")],
            "client": ("9.9.9.9", 1234),
        }
    )
    assert client_ip(request) == "1.2.3.4"


def test_rate_limit_returns_429(monkeypatch):
    app = create_app(
        Settings(
            database_url_readonly="postgresql://test",
            rate_limit="2/minute",
            db_pool_max_size=2,
        )
    )
    app.dependency_overrides[get_conn] = lambda: object()
    monkeypatch.setattr(
        "bailoteca_api.routers.academies.query_academies",
        lambda conn, **kwargs: ([], 0),
    )

    with TestClient(app) as client:
        assert client.get("/academies").status_code == 200
        assert client.get("/academies").status_code == 200
        response = client.get("/academies")

    assert response.status_code == 429
    assert response.json() == {
        "detail": "Demasiadas solicitudes. Intenta de nuevo más tarde."
    }
    assert "retry-after" in response.headers
