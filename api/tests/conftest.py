import pytest
from fastapi.testclient import TestClient

from bailoteca_api.config import Settings
from bailoteca_api.main import create_app


@pytest.fixture
def settings():
    return Settings(
        database_url_readonly="postgresql://test",
        cors_origins="http://localhost:4200",
        rate_limit="1000/minute",
        db_pool_max_size=2,
    )


@pytest.fixture
def client(settings):
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client
