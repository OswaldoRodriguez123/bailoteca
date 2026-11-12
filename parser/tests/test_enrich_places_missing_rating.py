from types import SimpleNamespace

from bailoteca.cli import build_parser, cmd_enrich_places
from bailoteca.places import PlaceInfo


class _MissingArgs:
    missing_rating = True
    force = False
    dry_run = False
    slug = None


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


def _patch_base(monkeypatch, fake_db):
    import bailoteca.cli as cli
    import bailoteca.db as db

    monkeypatch.setattr(cli, "_load_config", lambda: _FakeConfig())
    monkeypatch.setattr(db, "connect", lambda database_url: fake_db)
    monkeypatch.setattr(db, "list_published", lambda conn: list(conn._academies))


def test_merges_google_and_keeps_cover(monkeypatch):
    import bailoteca.places as places

    academy = {
        "id": "id-1", "slug": "sala", "name": "Sala", "status": "published",
        "google": {"place_id": "p1", "rating": None, "reviews": None,
                   "gps_coordinates": {"latitude": -33.4, "longitude": -70.6}},
        "cover_url": "https://cdn/old.jpg", "cover_source": "instagram",
        "locations": [{"comuna": "Santiago", "address": "Calle 1",
                       "lat": None, "lng": None}],
        "links": [], "styles": [],
    }
    fake_db = _FakeDB([academy])
    _patch_base(monkeypatch, fake_db)
    monkeypatch.setattr(
        places,
        "fetch_place",
        lambda *args, **kwargs: PlaceInfo(rating=4.6, reviews=12),
    )

    result = cmd_enrich_places(_MissingArgs())

    assert result == 0
    sql, params = fake_db.updates[-1]
    google = params[0].obj if hasattr(params[0], "obj") else params[0]
    assert google["rating"] == 4.6 and google["reviews"] == 12
    assert google["gps_coordinates"]["latitude"] == -33.4
    assert google["place_id"] == "p1"
    assert "cover_url" not in sql and "cover_source" not in sql


def test_skips_academies_with_rating(monkeypatch):
    import bailoteca.places as places

    academy = {"id": "id-1", "slug": "sala", "name": "Sala",
               "google": {"place_id": "p1", "rating": 4.8, "reviews": 100},
               "cover_url": None, "cover_source": None,
               "locations": [], "links": [], "styles": []}
    fake_db = _FakeDB([academy])
    _patch_base(monkeypatch, fake_db)
    calls = []
    monkeypatch.setattr(places, "fetch_place", lambda *a, **k: calls.append(1))

    result = cmd_enrich_places(_MissingArgs())

    assert result == 0
    assert calls == []
    assert fake_db.updates == []


def test_skips_academies_without_place_id(monkeypatch):
    import bailoteca.places as places

    academy = {"id": "id-1", "slug": "sala", "name": "Sala",
               "google": {"place_id": None, "rating": None},
               "cover_url": None, "cover_source": None,
               "locations": [], "links": [], "styles": []}
    fake_db = _FakeDB([academy])
    _patch_base(monkeypatch, fake_db)
    calls = []
    monkeypatch.setattr(places, "fetch_place", lambda *a, **k: calls.append(1))

    cmd_enrich_places(_MissingArgs())

    assert calls == []


def test_missing_rating_flag_parses():
    args = build_parser().parse_args(["enrich-places", "--missing-rating"])
    assert args.missing_rating is True
