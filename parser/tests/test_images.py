from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from bailoteca.images import _fetch_og_image, refresh_images


@pytest.fixture(autouse=True)
def _public_dns(monkeypatch):
    # Los tests usan hosts ficticios: simulamos DNS público para safe_url.
    monkeypatch.setattr(
        "bailoteca.enrich._resolve_host", lambda host: ["93.184.216.34"]
    )


class _FakeResponse:
    def __init__(self, status, body, content=b"", content_type="text/html", url=None, headers=None):
        self.status_code = status
        self.text = body
        self.content = content
        self.headers = headers if headers is not None else {"content-type": content_type}
        if url is not None:
            self.url = url


_HTML_WITH_OG = "<html><head><meta property=\"og:image\" content=\"https://img.example/cover.jpg\"></head></html>"


def _og_url() -> str:
    return "https://img.example/cover.jpg"


class _FakeHttp:
    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = 0

    def get(self, url, **kwargs):
        self.calls += 1
        if url in self.mapping:
            return self.mapping[url]
        raise AssertionError(f"unexpected url {url}")


_image_body = b"\xff\xd8" * 400  # jpeg magic + padding > 500 bytes


def test_fetch_og_image_happy_path():
    client = _FakeHttp({
        "https://ig.example/profile": _FakeResponse(200, _HTML_WITH_OG),
        "https://img.example/cover.jpg": _FakeResponse(200, _HTML_WITH_OG, _image_body, "image/jpeg"),
    })
    assert _fetch_og_image("https://ig.example/profile", client=client) == _og_url()


def test_fetch_og_image_missing_meta():
    client = _FakeHttp({
        "https://ig.example/profile": _FakeResponse(200, "<html>no meta</html>"),
    })
    assert _fetch_og_image("https://ig.example/profile", client=client) is None


def test_fetch_og_image_page_status_fail():
    client = _FakeHttp({
        "https://ig.example/profile": _FakeResponse(403, "<html></html>"),
    })
    assert _fetch_og_image("https://ig.example/profile", client=client) is None


def test_fetch_og_image_image_status_fail():
    client = _FakeHttp({
        "https://ig.example/profile": _FakeResponse(200, _HTML_WITH_OG),
        "https://img.example/cover.jpg": _FakeResponse(404, ""),
    })
    assert _fetch_og_image("https://ig.example/profile", client=client) is None


def test_fetch_og_image_image_too_small():
    client = _FakeHttp({
        "https://ig.example/profile": _FakeResponse(200, _HTML_WITH_OG),
        "https://img.example/cover.jpg": _FakeResponse(200, "", b"tiny", "image/jpeg"),
    })
    assert _fetch_og_image("https://ig.example/profile", client=client) is None


def test_fetch_og_image_rejects_instagram_static_logo():
    # Instagram devuelve su logo de UI (static.cdninstagram.com/rsrc.php/...)
    # como og:image cuando el scraper anónimo es bloqueado; no es contenido de la academia.
    html = (
        '<html><head><meta property="og:image" '
        'content="https://static.cdninstagram.com/rsrc.php/v4/yD/r/R0fBIMurK8v.png">'
        "</head></html>"
    )
    client = _FakeHttp({
        "https://ig.example/blocked": _FakeResponse(200, html),
        "https://static.cdninstagram.com/rsrc.php/v4/yD/r/R0fBIMurK8v.png": _FakeResponse(
            200, "<html></html>", _image_body, "image/png"
        ),
    })
    assert _fetch_og_image("https://ig.example/blocked", client=client) is None


def test_refresh_images_keeps_thumbnail_when_only_instagram_logo():
    academies = [
        {
            "id": "1",
            "slug": "logo-only",
            "name": "logo only",
            "status": "published",
            "google": {"thumbnail": "https://static.cdninstagram.com/rsrc.php/v4/yD/r/R0fBIMurK8v.png", "thumbnail_source": "instagram"},
            "locations": [],
            "links": [{"kind": "instagram", "url": "https://ig.example/logo"}],
            "styles": [],
        },
    ]
    fake_db = _FakeImagesDB(academies)
    import bailoteca.images as images_module
    images_module.connect = lambda url: fake_db
    images_module.list_published = lambda conn: list(conn._academies)

    html = (
        '<html><head><meta property="og:image" '
        'content="https://static.cdninstagram.com/rsrc.php/v4/yD/r/R0fBIMurK8v.png">'
        "</head></html>"
    )
    client = _FakeHttp({
        "https://ig.example/logo": _FakeResponse(200, html),
    })
    storage = _FakeStorage()
    summary = refresh_images(_FakeConfig(), client=client, storage=storage, dry_run=False)

    assert summary["updated"] == 0
    assert summary["no_image"] == 1
    assert summary["kept_google"] == 0
    assert storage.uploads == []
    assert fake_db._updated == []


class _FakeConfig:
    def __init__(self, database_url: str | None = None):
        self.database_url = database_url or "postgresql://noop"
        self.supabase_url = "https://proj.supabase.co"
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
        return f"{self.supabase_url}/storage/v1/object/public/{bucket}/{key}"

    @property
    def supabase_url(self):
        return "https://proj.supabase.co"


class _FakeImagesDB:
    def __init__(self, academies, published_name="published"):
        self._academies = academies
        self._commit = 0
        self._updated = []

    def execute(self, sql, params=()):
        if sql.strip().startswith("select id::text"):
            return SimpleNamespace(fetchall=lambda: list(self._academies))
        if sql.strip().startswith("update academies"):
            self._updated.append(params)
            return SimpleNamespace(rowcount=1)
        raise AssertionError(f"unexpected SQL {sql}")

    def commit(self):
        self._commit += 1

    def close(self):
        pass


class _FakeImagesResult:
    pass


def test_refresh_images_prefers_google_thumbnails():
    academies = [
        {
            "id": "1",
            "slug": "keep-google",
            "name": "keep google",
            "status": "published",
            "google": {"thumbnail": "https://g.example/x.jpg", "thumbnail_source": "google"},
            "locations": [],
            "links": [{"kind": "instagram", "url": "https://ig.example/keep"}],
            "styles": [],
        },
        {
            "id": "2",
            "slug": "update-me",
            "name": "update me",
            "status": "published",
            "google": None,
            "locations": [],
            "links": [{"kind": "instagram", "url": "https://ig.example/me"}],
            "styles": [],
        },
    ]
    fake_db = _FakeImagesDB(academies)
    client = _FakeHttp({
        "https://ig.example/me": _FakeResponse(200, _HTML_WITH_OG),
        "https://img.example/cover.jpg": _FakeResponse(200, _HTML_WITH_OG, _image_body, "image/jpeg"),
    })

    # monkeypatch connect to return fake db
    import bailoteca.images as images_module
    images_module.connect = lambda url: fake_db
    images_module.list_published = lambda conn: list(conn._academies)
    storage = _FakeStorage()

    summary = refresh_images(_FakeConfig(), client=client, storage=storage, dry_run=False)

    assert summary["kept_google"] == 1
    assert summary["updated"] == 1
    assert storage.uploads
    assert fake_db._commit == 1


def test_refresh_images_dry_run_does_not_write():
    academies = [
        {
            "id": "1",
            "slug": "dry-run",
            "name": "Dry",
            "status": "published",
            "google": None,
            "locations": [],
            "links": [{"kind": "instagram", "url": "https://ig.example/yes"}],
            "styles": [],
        },
    ]
    fake_db = _FakeImagesDB(academies)
    import bailoteca.images as images_module
    images_module.connect = lambda url: fake_db
    images_module.list_published = lambda conn: list(conn._academies)

    client = _FakeHttp({
        "https://ig.example/yes": _FakeResponse(200, _HTML_WITH_OG),
        "https://img.example/cover.jpg": _FakeResponse(200, _HTML_WITH_OG, _image_body, "image/jpeg"),
    })
    summary = refresh_images(_FakeConfig(), client=client, dry_run=True)
    assert summary["updated"] == 1
    assert fake_db._updated == []


def _cover_academy(slug, *, google, cover_url=None, age_days=0, links=None):
    return {
        "id": f"id-{slug}",
        "slug": slug,
        "name": slug,
        "status": "published",
        "google": google,
        "cover_url": cover_url,
        "cover_source": "instagram" if cover_url else None,
        "cover_fetched_at": datetime.now(timezone.utc) - timedelta(days=age_days) if cover_url or age_days else None,
        "locations": [],
        "links": links or [{"kind": "instagram", "url": f"https://ig.example/{slug}"}],
        "styles": [],
    }


def test_refresh_images_skips_fresh_cover_without_http_or_write():
    academy = _cover_academy(
        "fresh",
        google=None,
        cover_url="https://proj.supabase.co/storage/v1/object/public/academy-covers/fresh.jpg",
        age_days=10,
    )
    fake_db = _FakeImagesDB([academy])
    import bailoteca.images as images_module
    images_module.connect = lambda url: fake_db
    images_module.list_published = lambda conn: list(conn._academies)
    client = _FakeHttp({})
    storage = _FakeStorage()

    summary = refresh_images(_FakeConfig(), client=client, storage=storage, dry_run=False)

    assert summary["fresh"] == 1
    assert summary["updated"] == 0
    assert client.calls == 0
    assert storage.ensured == []
    assert storage.uploads == []
    assert fake_db._updated == []


def test_refresh_images_refreshes_stale_cover_and_hosts_it():
    academy = _cover_academy(
        "stale",
        google=None,
        cover_url="https://proj.supabase.co/storage/v1/object/public/academy-covers/stale.jpg",
        age_days=181,
    )
    fake_db = _FakeImagesDB([academy])
    import bailoteca.images as images_module
    images_module.connect = lambda url: fake_db
    images_module.list_published = lambda conn: list(conn._academies)
    client = _FakeHttp({
        "https://ig.example/stale": _FakeResponse(200, _HTML_WITH_OG),
        "https://img.example/cover.jpg": _FakeResponse(200, _HTML_WITH_OG, _image_body, "image/jpeg"),
    })
    storage = _FakeStorage()

    summary = refresh_images(_FakeConfig(), client=client, storage=storage, dry_run=False)

    assert summary["updated"] == 1
    assert summary["fresh"] == 0
    assert storage.ensured == ["academy-covers"]
    assert storage.uploads == [("academy-covers", "stale.jpg", _image_body, "image/jpeg")]
    assert fake_db._updated[0][0] == "https://proj.supabase.co/storage/v1/object/public/academy-covers/stale.jpg"
    assert fake_db._updated[0][1] == "instagram"


def test_refresh_images_keeps_cover_when_only_instagram_logo():
    academy = _cover_academy(
        "logo",
        google={"thumbnail": "https://static.cdninstagram.com/rsrc.php/R0fBIMurK8v.png"},
        cover_url="https://proj.supabase.co/storage/v1/object/public/academy-covers/logo.jpg",
        age_days=181,
    )
    html = (
        '<html><head><meta property="og:image" '
        'content="https://static.cdninstagram.com/rsrc.php/v4/yD/r/R0fBIMurK8v.png">'
        "</head></html>"
    )
    fake_db = _FakeImagesDB([academy])
    import bailoteca.images as images_module
    images_module.connect = lambda url: fake_db
    images_module.list_published = lambda conn: list(conn._academies)
    client = _FakeHttp({
        "https://ig.example/logo": _FakeResponse(200, html),
    })
    storage = _FakeStorage()

    summary = refresh_images(_FakeConfig(), client=client, storage=storage, dry_run=False)

    assert summary["no_image"] == 1
    assert summary["updated"] == 0
    assert storage.uploads == []
    assert fake_db._updated == []


def test_refresh_images_skips_place_linked_academy():
    academy = _cover_academy(
        "place",
        google={"place_id": "place-123"},
        cover_url="https://proj.supabase.co/storage/v1/object/public/academy-covers/place.jpg",
        age_days=181,
    )
    fake_db = _FakeImagesDB([academy])
    import bailoteca.images as images_module
    images_module.connect = lambda url: fake_db
    images_module.list_published = lambda conn: list(conn._academies)
    client = _FakeHttp({})
    storage = _FakeStorage()

    summary = refresh_images(_FakeConfig(), client=client, storage=storage, dry_run=False)

    assert summary["kept_google"] == 1
    assert client.calls == 0
    assert storage.uploads == []
    assert fake_db._updated == []


def test_fetch_og_image_rejects_private_page_url():
    client = _FakeHttp({})
    assert _fetch_og_image("http://127.0.0.1:8080/admin", client=client) is None
    assert client.calls == 0


def test_fetch_og_image_rejects_redirect_to_private_page():
    # El redirect NUNCA se sigue si el destino no es público.
    client = _FakeHttp({
        "https://ig.example/profile": _FakeResponse(
            302,
            "",
            url=None,
            headers={"content-type": "text/html", "location": "http://169.254.169.254/latest"},
        ),
    })
    assert _fetch_og_image("https://ig.example/profile", client=client) is None
    assert client.calls == 1  # solo la URL pública inicial


def test_fetch_og_image_rejects_private_og_target():
    html = '<html><head><meta property="og:image" content="http://127.0.0.1:8080/x.jpg"></head></html>'
    client = _FakeHttp({
        "https://ig.example/profile": _FakeResponse(200, html),
    })
    assert _fetch_og_image("https://ig.example/profile", client=client) is None


def test_fetch_og_image_rejects_oversized_image():
    from bailoteca.enrich import MAX_BYTES

    client = _FakeHttp({
        "https://ig.example/profile": _FakeResponse(200, _HTML_WITH_OG),
        "https://img.example/cover.jpg": _FakeResponse(
            200,
            "",
            b"\xff" * (MAX_BYTES + 1),
            "image/jpeg",
        ),
    })
    assert _fetch_og_image("https://ig.example/profile", client=client) is None
