from pathlib import Path

from directorio_baile.config import Config


def test_defaults_without_environment():
    cfg = Config.from_env({})
    assert cfg.database_url is None
    assert cfg.gemini_api_key is None
    assert cfg.serpapi_key is None
    assert cfg.cache_dir == Path("data/cache")
    assert cfg.reports_dir == Path("reports")
    assert cfg.sources == ["seed", "search"]


def test_reads_environment():
    cfg = Config.from_env(
        {
            "DATABASE_URL": "postgresql://u:p@host/db",
            "GEMINI_API_KEY": "g-key",
            "SERPAPI_KEY": "s-key",
            "DANCE_SOURCES": "seed,osm",
            "DANCE_CACHE_DIR": "/tmp/cache",
            "DANCE_REPORTS_DIR": "/tmp/reports",
        }
    )
    assert cfg.database_url == "postgresql://u:p@host/db"
    assert cfg.sources == ["seed", "osm"]
    assert cfg.cache_dir == Path("/tmp/cache")
