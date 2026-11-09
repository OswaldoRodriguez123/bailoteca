#!/usr/bin/env python
"""Ejecuta el spike de OSM contra un fixture o contra Overpass."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from directorio_baile.osm_spike import summarize
from directorio_baile.sources.osm import (
    GRAN_SANTIAGO_BBOX,
    OVERPASS_ENDPOINTS,
    build_query,
    parse_overpass,
)


def load_from_overpass(bbox) -> dict:
    import httpx

    query = build_query(bbox)
    last_error = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            response = httpx.post(endpoint, content=query, timeout=60.0)
            response.raise_for_status()
            return response.json()
        except Exception as error:  # noqa: BLE001 - el spike reporta el fallo
            last_error = error
    raise SystemExit(f"Overpass no respondió: {last_error}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        help="JSON de Overpass ya descargado; si falta, consulta la red",
    )
    args = parser.parse_args(argv)

    if args.fixture:
        data = json.loads(args.fixture.read_text(encoding="utf-8"))
        endpoint = f"fixture:{args.fixture}"
    else:
        data = load_from_overpass(GRAN_SANTIAGO_BBOX)
        endpoint = "overpass"

    summary = summarize(parse_overpass(data))
    result = {"endpoint": endpoint, "bbox": GRAN_SANTIAGO_BBOX, **summary}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
