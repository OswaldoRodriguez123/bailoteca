"""Reglas deterministas de ruido para URLs descubiertas.

Solo descartan URLs que estructuralmente no pueden ser la ficha de una
academia: directorios, contenido de redes y canciones/videos. No intentan
adivinar tema, ciudad ni si es una academia; eso lo decide Clef.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from bailoteca.models import Candidate

NOISE_DOMAINS = frozenset(
    {
        "salirsantiago.com",
        "dancetomic.com",
        "2x3.cl",
        "starofservice.cl",
        "tusclasesparticulares.cl",
        "superprof.cl",
        "emagister.cl",
        "tripadvisor.cl",
        "rappi.cl",
        "toliv.com",
        "shazam.com",
        "open.spotify.com",
        "spotify.link",
        "youtube.com",
        "youtu.be",
        "tiktok.com",
        "classpass.com",
        "meetup.com",
        "getbailar.com",
        "salsavida.com",
        "servisantiago.org",
        "greenparkeventos.cl",
        "portalpuentealto.cl",
    }
)

CONTENT_PATHS = (
    "/posts/",
    "/videos/",
    "/photos/",
    "/events/",
    "/albums/",
    "/permalink",
    "/reels/",
    "/clases-de-bachata-en-",
)

INSTAGRAM_CONTENT_PREFIXES = (
    "/popular/",
    "/p/",
    "/reel/",
    "/tv/",
    "/stories/",
    "/explore/",
    "/accounts/",
)


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def _path(url: str) -> str:
    return urlsplit(url).path or "/"


def _matches_noise_domain(host: str) -> bool:
    return any(host == domain or host.endswith("." + domain) for domain in NOISE_DOMAINS)


def is_noise(candidate: Candidate) -> bool:
    url = (candidate.url or "").strip()
    if not url.startswith(("http://", "https://")):
        return False  # sin URL o malformada: no se descarta por regla
    host = _host(url)
    if not host:
        return False
    if _matches_noise_domain(host):
        return True
    path = _path(url)
    if any(marker in path for marker in CONTENT_PATHS):
        return True
    if host == "instagram.com" and path.startswith(INSTAGRAM_CONTENT_PREFIXES):
        return True
    return False


def filter_noise(candidates: list[Candidate]) -> tuple[list[Candidate], int]:
    kept = [candidate for candidate in candidates if not is_noise(candidate)]
    return kept, len(candidates) - len(kept)
