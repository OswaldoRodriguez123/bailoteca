import csv
from pathlib import Path

from directorio_baile.models import Candidate
from directorio_baile.normalize import normalize_handle


def load_seed(path: Path) -> list[Candidate]:
    candidates: list[Candidate] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            name = (row.get("name") or "").strip()
            if not name:
                continue
            url = (row.get("url") or "").strip() or None
            instagram = (row.get("instagram") or "").strip() or None
            comuna = (row.get("comuna") or "").strip() or None
            candidates.append(
                Candidate(
                    name=name,
                    url=url,
                    handle=normalize_handle(instagram),
                    source="seed",
                    comuna=comuna,
                )
            )
    return candidates
