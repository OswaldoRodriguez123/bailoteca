"""Cliente mínimo para Supabase Storage (API REST, sin SDK)."""

from __future__ import annotations

import httpx
from typing import Any


class StorageClient:
    def __init__(
        self,
        base_url: str,
        service_key: str,
        *,
        timeout: float = 30.0,
        client: Any | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.service_key = service_key
        self._client = client or httpx.Client(timeout=timeout)

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.service_key}"}

    def ensure_bucket(self, bucket: str) -> None:
        response = self._client.get(
            f"{self.base_url}/storage/v1/bucket/{bucket}",
            headers=self._headers,
        )
        if getattr(response, "status_code", None) == 200:
            payload = response.json()
            if isinstance(payload, dict) and payload.get("public") is True:
                return
            raise RuntimeError(
                f"El bucket {bucket!r} existe pero no es público; no se toca un bucket ajeno."
            )
        if getattr(response, "status_code", None) != 404:
            raise RuntimeError(
                f"No se pudo consultar el bucket {bucket!r}: HTTP {getattr(response, 'status_code', 'unknown')}."
            )
        created = self._client.post(
            f"{self.base_url}/storage/v1/bucket",
            json={"id": bucket, "name": bucket, "public": True},
            headers=self._headers,
        )
        if getattr(created, "status_code", None) not in (200, 201):
            raise RuntimeError(
                f"No se pudo crear el bucket {bucket!r}: HTTP {getattr(created, 'status_code', 'unknown')}."
            )

    def upload(
        self,
        bucket: str,
        key: str,
        content: bytes,
        content_type: str = "image/jpeg",
    ) -> None:
        response = self._client.post(
            f"{self.base_url}/storage/v1/object/{bucket}/{key}",
            content=content,
            headers={
                **self._headers,
                "Content-Type": content_type,
                "x-upsert": "true",
            },
        )
        if getattr(response, "status_code", None) not in (200, 201):
            raise RuntimeError(
                f"No se pudo subir {bucket}/{key}: HTTP {getattr(response, 'status_code', 'unknown')}."
            )

    def public_url(self, bucket: str, key: str) -> str:
        return f"{self.base_url}/storage/v1/object/public/{bucket}/{key}"
