from __future__ import annotations

from typing import Protocol
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup

from directorio_baile.models import Candidate

SEARCH_DOMAINS = {
    "duckduckgo.com",
    "google.com",
    "bing.com",
    "yahoo.com",
    "yandex.com",
}
INSTAGRAM_POST_PREFIXES = ("/p/", "/reel/", "/tv/", "/stories/")


class HttpClient(Protocol):
    def get(self, url: str, params: dict | None = None): ...


def build_queries(comunas: list[str]) -> list[str]:
    queries: list[str] = []
    for comuna in comunas:
        queries.extend(
            [
                f"academia de salsa {comuna}",
                f"salsa cubana {comuna}",
                f"salsa en linea {comuna}",
                f"mambo {comuna}",
            ]
        )
    return queries


def _clean_href(href: str) -> str | None:
    if not href:
        return None
    if href.startswith("//"):
        href = f"https:{href}"
    parts = urlsplit(href)
    if parts.hostname and parts.hostname.endswith("duckduckgo.com"):
        uddg = parse_qs(parts.query).get("uddg")
        if uddg:
            href = uddg[0]
    if not href.startswith(("http://", "https://")):
        return None
    return href


def parse_ddg_html(html: str) -> list[Candidate]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[Candidate] = []
    for anchor in soup.select("a.result__a"):
        url = _clean_href(anchor.get("href") or "")
        if not url:
            continue
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        if host in SEARCH_DOMAINS:
            continue
        if host == "instagram.com" and parts.path.startswith(INSTAGRAM_POST_PREFIXES):
            continue
        name = anchor.get_text(" ", strip=True) or url
        handle = None
        if host == "instagram.com":
            handle = parts.path.strip("/").split("/")[0] or None
        candidates.append(
            Candidate(name=name, url=url, handle=handle, source="ddg")
        )
    return candidates


class DuckDuckGoSource:
    name = "ddg"

    def __init__(self, queries: list[str], http: HttpClient, delay: float = 1.0):
        self.queries = queries
        self.http = http
        self.delay = delay

    def discover(self) -> list[Candidate]:
        candidates: list[Candidate] = []
        for query in self.queries:
            response = self.http.get(
                "https://html.duckduckgo.com/html/", params={"q": query}
            )
            if response.status_code == 200:
                candidates.extend(parse_ddg_html(response.text))
        return candidates
