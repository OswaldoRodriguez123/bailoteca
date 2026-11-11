from types import SimpleNamespace

from bailoteca.config import Config, load
from bailoteca.supabase_storage import StorageClient


class _FakeResponse:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self._payload = payload
        self.text = text
        self.content = b""

    def json(self):
        return self._payload


class _FakeHttp:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_ensure_bucket_ok_when_public():
    http = _FakeHttp([_FakeResponse(200, {"id": "academy-covers", "public": True})])
    client = StorageClient("https://proj.supabase.co", "secret", client=http)

    client.ensure_bucket("academy-covers")

    assert http.calls[0][0] == "GET"
    assert http.calls[0][1] == "https://proj.supabase.co/storage/v1/bucket/academy-covers"


def test_ensure_bucket_creates_when_missing():
    http = _FakeHttp([
        _FakeResponse(404, {"message": "not found"}),
        _FakeResponse(200, {"id": "academy-covers", "public": True}),
    ])
    client = StorageClient("https://proj.supabase.co", "secret", client=http)

    client.ensure_bucket("academy-covers")

    method, url, kwargs = http.calls[1]
    assert method == "POST"
    assert url == "https://proj.supabase.co/storage/v1/bucket"
    assert kwargs["json"] == {"id": "academy-covers", "name": "academy-covers", "public": True}
    assert kwargs["headers"]["Authorization"] == "Bearer secret"


def test_ensure_bucket_private_bucket_raises():
    http = _FakeHttp([_FakeResponse(200, {"id": "academy-covers", "public": False})])
    client = StorageClient("https://proj.supabase.co", "secret", client=http)

    try:
        client.ensure_bucket("academy-covers")
    except RuntimeError as exc:
        assert "academy-covers" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_upload_sends_upsert_header_and_bytes():
    http = _FakeHttp([_FakeResponse(200, {"Key": "academy-covers/slug.jpg"})])
    client = StorageClient("https://proj.supabase.co", "secret", client=http)

    client.upload("academy-covers", "slug.jpg", b"jpeg-bytes", "image/jpeg")

    method, url, kwargs = http.calls[0]
    assert method == "POST"
    assert url == "https://proj.supabase.co/storage/v1/object/academy-covers/slug.jpg"
    assert kwargs["content"] == b"jpeg-bytes"
    assert kwargs["headers"]["x-upsert"] == "true"
    assert kwargs["headers"]["Content-Type"] == "image/jpeg"
    assert kwargs["headers"]["Authorization"] == "Bearer secret"


def test_public_url_format():
    client = StorageClient("https://proj.supabase.co/", "secret", client=_FakeHttp([]))

    assert (
        client.public_url("academy-covers", "slug.jpg")
        == "https://proj.supabase.co/storage/v1/object/public/academy-covers/slug.jpg"
    )


def test_config_reads_supabase_environment(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")

    cfg = load()

    assert cfg.supabase_url == "https://proj.supabase.co"
    assert cfg.supabase_service_role_key == "secret"


def test_config_defaults_supabase_to_none():
    cfg = Config.from_env({})

    assert cfg.supabase_url is None
    assert cfg.supabase_service_role_key is None
