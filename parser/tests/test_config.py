from pathlib import Path

from bailoteca.config import Config


def test_defaults_without_environment():
    cfg = Config.from_env({})
    assert cfg.database_url is None
    assert cfg.gemini_api_key is None
    assert cfg.serpapi_key is None
    assert cfg.cloudflare_account_id is None
    assert cfg.cloudflare_token is None
    assert cfg.resend_api_key is None
    assert cfg.review_to_email is None
    assert cfg.review_from_email == "onboarding@resend.dev"
    assert cfg.cache_dir == Path("data/cache")
    assert cfg.reports_dir == Path("reports")
    assert cfg.sources == ["seed", "search"]


def test_reads_environment():
    cfg = Config.from_env(
        {
            "DATABASE_URL": "postgresql://u:p@host/db",
            "GEMINI_API_KEY": "g-key",
            "SERPAPI_KEY": "s-key",
            "CLOUDFLARE_ACCOUNT_ID": "acct",
            "CLOUDFLARE_API_TOKEN": "tok",
            "BAILOTECA_SOURCES": "seed,osm",
            "BAILOTECA_CACHE_DIR": "/tmp/cache",
            "BAILOTECA_REPORTS_DIR": "/tmp/reports",
        }
    )
    assert cfg.database_url == "postgresql://u:p@host/db"
    assert cfg.cloudflare_account_id == "acct"
    assert cfg.cloudflare_token == "tok"
    assert cfg.sources == ["seed", "osm"]
    assert cfg.cache_dir == Path("/tmp/cache")
    assert cfg.reports_dir == Path("/tmp/reports")


def test_reads_resend_environment():
    cfg = Config.from_env(
        {
            "RESEND_API_KEY": "re_key",
            "BAILOTECA_REVIEW_TO_EMAIL": "yo@example.com",
            "BAILOTECA_REVIEW_FROM_EMAIL": "avisos@example.com",
        }
    )
    assert cfg.resend_api_key == "re_key"
    assert cfg.review_to_email == "yo@example.com"
    assert cfg.review_from_email == "avisos@example.com"
