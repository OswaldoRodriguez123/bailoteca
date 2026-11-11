import time
from types import SimpleNamespace

from bailoteca.images import _fetch_og_image, refresh_images


class _FakeResponse:
    def __init__(self, status, body, content=b"", content_type="text/html"):
        self.status_code = status
        self.text = body
        self.content = content
        self.headers = {"content-type": content_type}


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
            "google": {"thumbnail": "https://cdn.example/keep.jpg", "thumbnail_source": "instagram"},
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
        "https://static.cdninstagram.com/rsrc.php/v4/yD/r/R0fBIMurK8v.png": _FakeResponse(
            200, "<html></html>", _image_body, "image/png"
        ),
    })
    summary = refresh_images(_FakeConfig(), client=client, dry_run=False)

    assert summary["updated"] == 0
    assert summary["no_image"] == 1
    assert fake_db._updated == []


class _FakeConfig:
    def __init__(self, database_url: str | None = None):
        self.database_url = database_url or "postgresql://noop"


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

    summary = refresh_images(_FakeConfig(), client=client, dry_run=False)

    assert summary["kept_google"] == 1
    assert summary["updated"] == 1
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
