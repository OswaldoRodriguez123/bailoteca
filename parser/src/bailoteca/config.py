from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
import os


@dataclass(frozen=True)
class Config:
    database_url: str | None
    gemini_api_key: str | None
    serpapi_key: str | None
    brave_api_key: str | None
    tinyfish_api_key: str | None
    cloudflare_account_id: str | None
    cloudflare_token: str | None
    resend_api_key: str | None
    review_to_email: str | None
    review_from_email: str
    supabase_url: str | None
    supabase_service_role_key: str | None
    cache_dir: Path
    reports_dir: Path
    sources: list[str]

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Config":
        raw_sources = env.get("BAILOTECA_SOURCES", "seed,search")
        sources = [s.strip() for s in raw_sources.split(",") if s.strip()]
        return cls(
            database_url=env.get("DATABASE_URL") or None,
            gemini_api_key=env.get("GEMINI_API_KEY") or None,
            serpapi_key=env.get("SERPAPI_KEY") or None,
            brave_api_key=env.get("BRAVE_API_KEY") or None,
            tinyfish_api_key=env.get("TINYFISH_API_KEY") or None,
            cloudflare_account_id=env.get("CLOUDFLARE_ACCOUNT_ID") or None,
            cloudflare_token=env.get("CLOUDFLARE_API_TOKEN") or None,
            resend_api_key=env.get("RESEND_API_KEY") or None,
            review_to_email=env.get("BAILOTECA_REVIEW_TO_EMAIL") or None,
            review_from_email=env.get("BAILOTECA_REVIEW_FROM_EMAIL")
            or "onboarding@resend.dev",
            supabase_url=env.get("SUPABASE_URL") or None,
            supabase_service_role_key=env.get("SUPABASE_SERVICE_ROLE_KEY") or None,
            cache_dir=Path(env.get("BAILOTECA_CACHE_DIR", "data/cache")),
            reports_dir=Path(env.get("BAILOTECA_REPORTS_DIR", "reports")),
            sources=sources,
        )


def load() -> Config:
    return Config.from_env(os.environ)
