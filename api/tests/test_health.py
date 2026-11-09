from fastapi.testclient import TestClient

from bailoteca_api.main import create_app


def test_health_ok(client, monkeypatch):
    monkeypatch.setattr(
        "bailoteca_api.routers.health.check_db", lambda settings: True
    )
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_degraded(client, monkeypatch):
    monkeypatch.setattr(
        "bailoteca_api.routers.health.check_db", lambda settings: False
    )
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "error"}


def test_unhandled_error_returns_500(settings):
    app = create_app(settings)

    @app.get("/boom")
    def boom():
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"detail": "Error interno"}
