def test_cors_allows_configured_origin(client):
    response = client.options(
        "/academies",
        headers={
            "Origin": "http://localhost:4200",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "http://localhost:4200"
    )
