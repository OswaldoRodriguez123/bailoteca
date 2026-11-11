from datetime import datetime, timezone
from types import SimpleNamespace

from bailoteca.cli import cmd_enrich_places
from bailoteca.places import PlaceInfo


class _FakeArgs:
    dry_run = False
    slug = None
    force = False


class _FakeConfig:
    database_url = "postgresql://noop"
    serpapi_key = "serpapi-key"
    supabase_url = "https://proj.supabase.co"
    supabase_service_role_key = "secret"


class _FakeDB:
    def __init__(self, academies):
        self._academies = academies
        self.updates = []

    def execute(self, sql, params=()):
        self.updates.append((sql, params))
        return SimpleNamespace(rowcount=1)

    def commit(self):
        pass

    def close(self):
        pass


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


def test_enrich_places_hosts_thumbnail_and_omits_it_from_google(monkeypatch):
    import bailoteca.cli as cli
    import bailoteca.covers as covers
    import bailoteca.db as db
    import bailoteca.places as places
    import bailoteca.supabase_storage as storage_module

    academy = {
        "id": "academy-id",
        "slug": "google-academy",
        "name": "Google Academy",
        "status": "published",
        "google": None,
        "locations": [{"comuna": "Santiago", "address": "Calle 1", "lat": None, "lng": None}],
        "links": [],
        "styles": [],
    }
    fake_db = _FakeDB([academy])
    fake_storage = _FakeStorage()

    monkeypatch.setattr(cli, "_load_config", lambda: _FakeConfig())
    monkeypatch.setattr(db, "connect", lambda database_url: fake_db)
    monkeypatch.setattr(db, "list_published", lambda conn: list(conn._academies))
    monkeypatch.setattr(
        places,
        "fetch_place",
        lambda *args, **kwargs: PlaceInfo(
            place_id="place-id",
            name="Google Academy",
            thumbnail="https://lh3.googleusercontent.com/x",
            fetched_at=datetime(2026, 11, 11, tzinfo=timezone.utc),
        ),
    )
    monkeypatch.setattr(
        covers,
        "download_image",
        lambda url, *, client=None, timeout=20.0: b"\xff\xd8" * 400,
    )
    monkeypatch.setattr(
        storage_module,
        "StorageClient",
        lambda base_url, service_key: fake_storage,
    )

    result = cmd_enrich_places(_FakeArgs())

    assert result == 0
    assert fake_storage.ensured == ["academy-covers"]
    assert fake_storage.uploads == [
        ("academy-covers", "google-academy.jpg", b"\xff\xd8" * 400, "image/jpeg")
    ]
    sql, params = fake_db.updates[0]
    assert "cover_url = %s" in sql
    assert "cover_source = %s" in sql
    assert params[0].obj == {
        "place_id": "place-id",
        "name": "Google Academy",
        "address": None,
        "rating": None,
        "reviews": None,
        "price": None,
        "hours": None,
        "open_state": None,
        "maps_url": None,
        "phone": None,
        "website": None,
        "type": None,
        "gps_coordinates": None,
        "raw": None,
        "fetched_at": "2026-11-11T00:00:00+00:00",
    }
    assert params[1] == "https://proj.supabase.co/storage/v1/object/public/academy-covers/google-academy.jpg"
    assert params[2] == "google"
    assert params[3] == "academy-id"
