from types import SimpleNamespace

import pytest

from bailoteca.covers import BUCKET, download_image


@pytest.fixture(autouse=True)
def _public_dns(monkeypatch):
    # Los tests usan hosts ficticios: simulamos DNS público para safe_url.
    monkeypatch.setattr(
        "bailoteca.enrich._resolve_host", lambda host: ["93.184.216.34"]
    )


class _FakeResponse:
    def __init__(self, status, body="", content=b"", content_type="text/html", url=None, headers=None):
        self.status_code = status
        self.text = body
        self.content = content
        self.headers = headers if headers is not None else {"content-type": content_type}
        if url is not None:
            self.url = url


class _FakeHttp:
    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.mapping.get(url)
        if response is None:
            raise AssertionError(f"unexpected url {url}")
        if isinstance(response, Exception):
            raise response
        return response


_image_body = b"\xff\xd8" * 400


def test_download_image_accepts_image_response():
    client = _FakeHttp({
        "https://img.example/cover.jpg": _FakeResponse(
            200, content=_image_body, content_type="image/jpeg"
        ),
    })

    assert download_image("https://img.example/cover.jpg", client=client) == _image_body


def test_download_image_rejects_non_200():
    client = _FakeHttp({
        "https://img.example/cover.jpg": _FakeResponse(
            404, content=_image_body, content_type="image/jpeg"
        ),
    })

    assert download_image("https://img.example/cover.jpg", client=client) is None


def test_download_image_rejects_small_body():
    client = _FakeHttp({
        "https://img.example/cover.jpg": _FakeResponse(
            200, content=b"tiny", content_type="image/jpeg"
        ),
    })

    assert download_image("https://img.example/cover.jpg", client=client) is None


def test_download_image_rejects_non_image_content_type():
    client = _FakeHttp({
        "https://img.example/cover.jpg": _FakeResponse(
            200, content=_image_body, content_type="text/html"
        ),
    })

    assert download_image("https://img.example/cover.jpg", client=client) is None


class _FakeConfig:
    def __init__(self, supabase_url="https://proj.supabase.co"):
        self.database_url = "postgresql://noop"
        self.supabase_url = supabase_url
        self.supabase_service_role_key = "secret"


class _FakeStorage:
    def __init__(self):
        self.ensured = []
        self.uploads = []

    def ensure_bucket(self, bucket):
        self.ensured.append(bucket)

    def upload(self, bucket, key, content, content_type="image/jpeg"):
        self.uploads.append((bucket, key, content, content_type))

    def public_url(self, bucket, key):
        return f"https://proj.supabase.co/storage/v1/object/public/{bucket}/{key}"


class _FakeCoversDB:
    def __init__(self, academies):
        self._academies = academies
        self.updates = []

    def execute(self, sql, params=()):
        if sql.strip().startswith("update academies"):
            self.updates.append((sql, params))
            return SimpleNamespace(rowcount=1)
        raise AssertionError(f"unexpected SQL {sql}")

    def commit(self):
        pass

    def close(self):
        pass


def _academy(slug, *, google=None, cover_url=None, links=None):
    return {
        "id": f"id-{slug}",
        "slug": slug,
        "name": slug,
        "status": "published",
        "google": google,
        "cover_url": cover_url,
        "links": links or [],
        "locations": [],
        "styles": [],
    }


def _run_backfill(monkeypatch, academies, recovered_sources, client, storage=None):
    import bailoteca.covers as covers

    fake_db = _FakeCoversDB(academies)
    monkeypatch.setattr(covers, "connect", lambda database_url: fake_db)
    monkeypatch.setattr(covers, "list_published", lambda conn: list(conn._academies))
    fake_storage = storage or _FakeStorage()
    summary = covers.backfill_covers(
        _FakeConfig(), recovered_sources, storage=fake_storage, client=client
    )
    return summary, fake_db, fake_storage


def test_backfill_skips_cover_already_hosted(monkeypatch):
    academy = _academy(
        "hosted",
        cover_url="https://proj.supabase.co/storage/v1/object/public/academy-covers/hosted.jpg",
    )
    client = _FakeHttp({})

    summary, db, storage = _run_backfill(monkeypatch, [academy], {}, client)

    assert summary == {"hosted": [], "skipped": ["hosted"], "missing": [], "failed": []}
    assert client.calls == []
    assert storage.uploads == []
    assert db.updates == []


def test_backfill_uses_recovered_source_over_current_logo(monkeypatch):
    academy = _academy(
        "broken",
        google={
            "thumbnail": "https://static.cdninstagram.com/rsrc.php/x.png",
            "thumbnail_source": "instagram",
        },
    )
    client = _FakeHttp({
        "https://scontent.example/cover.jpg": _FakeResponse(
            200, content=_image_body, content_type="image/jpeg"
        ),
    })

    summary, db, storage = _run_backfill(
        monkeypatch,
        [academy],
        {"broken": "https://scontent.example/cover.jpg"},
        client,
    )

    assert summary["hosted"] == ["broken"]
    assert storage.uploads == [
        (BUCKET, "broken.jpg", _image_body, "image/jpeg")
    ]
    assert db.updates[0][1][0] == "https://proj.supabase.co/storage/v1/object/public/academy-covers/broken.jpg"
    assert db.updates[0][1][1] == "instagram"


def test_backfill_uses_existing_external_google_thumbnail(monkeypatch):
    academy = _academy(
        "external",
        google={"thumbnail": "https://example.com/cover.jpg"},
    )
    client = _FakeHttp({
        "https://example.com/cover.jpg": _FakeResponse(
            200, content=_image_body, content_type="image/jpeg"
        ),
    })

    summary, db, _ = _run_backfill(monkeypatch, [academy], {}, client)

    assert summary["hosted"] == ["external"]
    assert db.updates[0][1][0].endswith("/external.jpg")
    assert db.updates[0][1][1] == "web"


def test_backfill_records_failed_download_without_touching_db(monkeypatch):
    academy = _academy(
        "dead",
        google={"thumbnail": "https://example.com/dead.jpg"},
    )
    client = _FakeHttp({
        "https://example.com/dead.jpg": _FakeResponse(
            404, content=_image_body, content_type="image/jpeg"
        ),
    })

    summary, db, storage = _run_backfill(monkeypatch, [academy], {}, client)

    assert summary["failed"] == ["dead"]
    assert storage.uploads == []
    assert db.updates == []


def test_backfill_reports_missing_when_no_source(monkeypatch):
    academy = _academy("no-source", google=None)
    client = _FakeHttp({})

    summary, db, storage = _run_backfill(monkeypatch, [academy], {}, client)

    assert summary["missing"] == ["no-source"]
    assert db.updates == []
    assert storage.uploads == []


def test_backfill_dry_run_does_not_upload_or_write(monkeypatch):
    academy = _academy(
        "dry",
        google={"thumbnail": "https://example.com/cover.jpg"},
    )
    client = _FakeHttp({
        "https://example.com/cover.jpg": _FakeResponse(
            200, content=_image_body, content_type="image/jpeg"
        ),
    })

    import bailoteca.covers as covers

    fake_db = _FakeCoversDB([academy])
    monkeypatch.setattr(covers, "connect", lambda database_url: fake_db)
    monkeypatch.setattr(covers, "list_published", lambda conn: list(conn._academies))
    storage = _FakeStorage()

    summary = covers.backfill_covers(
        _FakeConfig(), {}, dry_run=True, storage=storage, client=client
    )

    assert summary["hosted"] == ["dry"]
    assert storage.uploads == []
    assert fake_db.updates == []


def test_download_image_rejects_private_ip_url():
    # IP literal privada/loopback: se rechaza sin llamar al cliente.
    client = _FakeHttp({})
    assert download_image("http://127.0.0.1:8080/cover.jpg", client=client) is None
    assert download_image("http://169.254.169.254/latest/meta-data", client=client) is None
    assert client.calls == []


def test_download_image_rejects_redirect_to_private_final_url():
    client = _FakeHttp({
        "https://img.example/cover.jpg": _FakeResponse(
            200,
            content=_image_body,
            content_type="image/jpeg",
            url="http://169.254.169.254/cover.jpg",
        ),
    })

    assert download_image("https://img.example/cover.jpg", client=client) is None


def test_download_image_rejects_oversized_content_length():
    from bailoteca.enrich import MAX_BYTES

    client = _FakeHttp({
        "https://img.example/cover.jpg": _FakeResponse(
            200,
            content=b"small",
            content_type="image/jpeg",
            headers={"content-type": "image/jpeg", "content-length": str(MAX_BYTES + 1)},
        ),
    })

    assert download_image("https://img.example/cover.jpg", client=client) is None


def test_download_image_rejects_oversized_body():
    from bailoteca.enrich import MAX_BYTES

    client = _FakeHttp({
        "https://img.example/cover.jpg": _FakeResponse(
            200,
            content=b"\xff" * (MAX_BYTES + 1),
            content_type="image/jpeg",
        ),
    })

    assert download_image("https://img.example/cover.jpg", client=client) is None
