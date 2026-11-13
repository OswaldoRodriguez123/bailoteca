from fastapi.testclient import TestClient
from starlette.requests import Request

from bailoteca_api.config import Settings
from bailoteca_api.db import get_conn
from bailoteca_api.main import create_app
from bailoteca_api.rate_limit import client_ip


def _request_with(headers: list[tuple[bytes, bytes]]) -> Request:
    return Request(
        {
            "type": "http",
            "headers": headers,
            "client": ("9.9.9.9", 1234),
        }
    )


def test_client_ip_uses_last_forwarded_for_hop():
    # Detrás de un proxy que añade (append), el hop más a la derecha es el
    # que observó el proxy más externo; el izquierdo lo escribe el cliente.
    request = _request_with([(b"x-forwarded-for", b"1.2.3.4, 5.6.7.8")])
    assert client_ip(request) == "5.6.7.8"


def test_client_ip_prefers_vercel_headers():
    request = _request_with(
        [
            (b"x-forwarded-for", b"1.2.3.4, 5.6.7.8"),
            (b"x-vercel-forwarded-for", b"9.8.7.6"),
            (b"x-real-ip", b"7.7.7.7"),
        ]
    )
    assert client_ip(request) == "9.8.7.6"


def test_client_ip_leftmost_spoofing_shares_bucket():
    # Regresión: dos requests con distinto primer hop (controlado por el
    # cliente) y mismo último hop deben derivar la misma clave.
    first = _request_with([(b"x-forwarded-for", b"1.1.1.1, 203.0.113.10")])
    second = _request_with([(b"x-forwarded-for", b"2.2.2.2, 203.0.113.10")])
    assert client_ip(first) == client_ip(second) == "203.0.113.10"


def test_client_ip_falls_back_to_peer_address():
    request = _request_with([])
    assert client_ip(request) == "9.9.9.9"


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
