"""Contrato de respuesta compartido entre el parser y la API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AcademyLocation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str | None = None
    address: str | None = None
    comuna: str | None = None
    lat: float | None = None
    lng: float | None = None
    source_url: str | None = None


class AcademyLink(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kind: str
    url: str


class AcademyStyle(BaseModel):
    model_config = ConfigDict(extra="ignore")

    slug: str
    name: str | None = None
    confidence: float | None = None
    evidence: str | None = None


class GooglePlace(BaseModel):
    model_config = ConfigDict(extra="ignore")

    place_id: str | None = None
    name: str | None = None
    address: str | None = None
    rating: float | None = None
    reviews: int | None = None
    price: str | None = None
    hours: dict | None = None
    open_state: str | None = None
    maps_url: str | None = None
    fetched_at: datetime | None = None


class Academy(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    slug: str
    name: str
    description: str | None = None
    status: str
    source_urls: list[str] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None
    verified_at: datetime | None = None
    locations: list[AcademyLocation] = []
    links: list[AcademyLink] = []
    styles: list[AcademyStyle] = []
    google: GooglePlace | None = None
