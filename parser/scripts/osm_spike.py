#!/usr/bin/env python
"""Ejecuta el spike de OSM contra un fixture o contra Overpass."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bailoteca.osm_spike import summarize
from bailoteca.sources.osm import GRAN_SANTIAGO_BBOX, OverpassSource, parse_overpass


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
        candidates = parse_overpass(data)
        endpoint = f"fixture:{args.fixture}"
    else:
        candidates = OverpassSource().discover()
        endpoint = "overpass"

    summary = summarize(candidates)
    result = {"endpoint": endpoint, "bbox": list(GRAN_SANTIAGO_BBOX), **summary}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
