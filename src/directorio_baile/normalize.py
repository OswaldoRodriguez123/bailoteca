import hashlib
import json
import re
import unicodedata
from urllib.parse import urlsplit

from slugify import slugify as _slugify

GENERIC_WORDS = {
    "academia",
    "escuela",
    "estudio",
    "clases",
    "de",
    "del",
    "la",
    "el",
    "los",
    "las",
    "y",
}


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize_name(name: str) -> str:
    text = strip_accents(name).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    words = [word for word in text.split() if word not in GENERIC_WORDS]
    return " ".join(words)


def slugify(text: str) -> str:
    return _slugify(text)


def domain_of(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url.strip())
    host = parts.hostname
    if not host:
        return None
    return host[4:] if host.startswith("www.") else host


def normalize_handle(handle: str | None) -> str | None:
    if handle is None:
        return None
    cleaned = handle.strip().lstrip("@").lower()
    return cleaned or None


def candidate_key(
    name: str,
    url: str | None,
    handle: str | None,
    comuna: str | None,
) -> str:
    identifier = domain_of(url)
    if identifier is None:
        normalized_handle = normalize_handle(handle)
        if normalized_handle:
            identifier = f"ig:{normalized_handle}"
        else:
            identifier = normalize_name(comuna) if comuna else ""
    return f"{normalize_name(name)}|{identifier}"


def payload_hash(payload: dict) -> str:
    serialized = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
