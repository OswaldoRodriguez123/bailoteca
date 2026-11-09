from datetime import datetime, timedelta, timezone

from bailoteca.report import stale_academies


def test_stale_academies_includes_unverified_and_old():
    now = datetime(2026, 11, 9, tzinfo=timezone.utc)
    academies = [
        {"name": "A", "verified_at": None},
        {"name": "B", "verified_at": now - timedelta(days=100)},
        {"name": "C", "verified_at": now - timedelta(days=10)},
    ]
    assert [item["name"] for item in stale_academies(academies, now=now)] == [
        "A",
        "B",
    ]
