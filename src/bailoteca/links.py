"""Comprobación de enlaces publicados."""

from __future__ import annotations

from typing import Protocol

import psycopg

from bailoteca.db import list_published

RETRYABLE_HEAD_STATUS = {405, 501}
CHECKABLE_KINDS = {"web", "instagram", "facebook", "tiktok", "whatsapp"}


class HttpClient(Protocol):
    def head(self, url: str): ...

    def get(self, url: str): ...


def check_link(url: str, http: HttpClient) -> str:
    try:
        response = http.head(url)
    except Exception:
        return "unknown"
    status = getattr(response, "status_code", 0)
    if status in RETRYABLE_HEAD_STATUS:
        try:
            response = http.get(url)
        except Exception:
            return "unknown"
        status = getattr(response, "status_code", 0)
    if 200 <= status < 300:
        return "ok"
    if status in (404, 410):
        return "dead"
    if status in (403, 429):
        return "blocked"
    return "unknown"


def check_published(
    conn: psycopg.Connection, http: HttpClient
) -> list[dict]:
    dead: list[dict] = []
    for academy in list_published(conn):
        for link in academy["links"]:
            if link["kind"] not in CHECKABLE_KINDS:
                continue
            status = check_link(link["url"], http)
            if status == "dead":
                dead.append(
                    {
                        "academy_id": academy["id"],
                        "slug": academy["slug"],
                        "name": academy["name"],
                        "kind": link["kind"],
                        "url": link["url"],
                        "status": status,
                    }
                )
    return dead
