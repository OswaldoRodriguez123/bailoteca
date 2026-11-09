import os

import pytest

from bailoteca.db import (
    academy_id_by_slug,
    connect,
    insert_proposal,
    list_published,
    pending_proposals,
    record_field_rejections,
    rejected_values,
    upsert_candidate,
)
from bailoteca.models import Candidate
from bailoteca.publish import approve

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


def test_list_published_does_not_duplicate_relations(conn):
    cand = Candidate(
        "Academia Relaciones", "https://relaciones.cl", None, "seed", "Providencia"
    )
    candidate_id = upsert_candidate(conn, cand)
    payload = {
        "name": "Academia Relaciones",
        "description": "Salsa.",
        "locations": [
            {"label": "Sede 1", "address": "Av. 1", "comuna": "Providencia"},
            {"label": "Sede 2", "address": "Av. 2", "comuna": "Ñuñoa"},
        ],
        "links": [
            {"kind": "web", "url": "https://relaciones.cl"},
            {"kind": "instagram", "url": "https://instagram.com/relaciones"},
        ],
        "styles": [
            {"slug": "salsa-cubana", "confidence": 0.9},
            {"slug": "salsa-linea", "confidence": 0.9},
        ],
    }
    proposal_id = insert_proposal(
        conn,
        candidate_id=candidate_id,
        academy_id=None,
        kind="create",
        payload=payload,
        evidence={},
        confidence=1.0,
    )
    academy_id = approve(conn, proposal_id)

    row = next(a for a in list_published(conn) if a["id"] == academy_id)
    assert len(row["locations"]) == 2
    assert len(row["links"]) == 2
    assert len(row["styles"]) == 2
