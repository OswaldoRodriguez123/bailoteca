import os

import pytest

from directorio_baile.db import (
    academy_id_by_slug,
    connect,
    insert_proposal,
    pending_proposals,
    record_field_rejections,
    rejected_values,
    upsert_candidate,
)
from directorio_baile.models import Candidate

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set",
)


@pytest.fixture()
def conn():
    connection = connect(os.environ["TEST_DATABASE_URL"])
    yield connection
    connection.rollback()
    connection.close()


def test_upsert_candidate_is_idempotent(conn):
    cand = Candidate("Academia Demo", "https://demo.cl", None, "seed", "Providencia")
    first = upsert_candidate(conn, cand)
    second = upsert_candidate(conn, cand)
    assert first == second


def test_duplicate_proposal_is_ignored(conn):
    cand = Candidate("Academia Demo 2", "https://demo2.cl", None, "seed")
    candidate_id = upsert_candidate(conn, cand)
    kwargs = dict(
        candidate_id=candidate_id,
        academy_id=None,
        kind="create",
        payload={"name": "Academia Demo 2"},
        evidence={"name": {"source_url": "https://demo2.cl", "confidence": 0.9}},
        confidence=0.9,
    )
    assert insert_proposal(conn, **kwargs) is not None
    assert insert_proposal(conn, **kwargs) is None


def test_pending_and_rejections(conn):
    cand = Candidate("Academia Demo 3", "https://demo3.cl", None, "seed")
    candidate_id = upsert_candidate(conn, cand)
    proposal_id = insert_proposal(
        conn,
        candidate_id=candidate_id,
        academy_id=None,
        kind="create",
        payload={"name": "Academia Demo 3"},
        evidence={},
        confidence=0.9,
    )
    assert proposal_id in {p["id"] for p in pending_proposals(conn)}
    row = conn.execute(
        "insert into academies (slug, name) values ('demo-3', 'Demo 3') returning id"
    ).fetchone()
    record_field_rejections(conn, row["id"], [("address", "hash-1")])
    assert ("address", "hash-1") in rejected_values(conn, row["id"])
    assert academy_id_by_slug(conn, "demo-3") == row["id"]
