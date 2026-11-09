import os

import pytest

from bailoteca.db import (
    connect,
    insert_proposal,
    rejected_values,
    upsert_candidate,
)
from bailoteca.models import Candidate
from bailoteca.propose import field_value_hash
from bailoteca.publish import approve, reject

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set",
)


@pytest.fixture()
def conn():
    c = connect(os.environ["TEST_DATABASE_URL"])
    yield c
    c.rollback()
    c.close()


def test_approve_create_publishes_and_verifies(conn):
    cand = Candidate("Academia Nueva", "https://nueva.cl", None, "seed", "Providencia")
    cid = upsert_candidate(conn, cand)
    pid = insert_proposal(
        conn,
        candidate_id=cid,
        academy_id=None,
        kind="create",
        payload={
            "name": "Academia Nueva",
            "description": "Salsa.",
            "locations": [{"address": "Av. 1", "comuna": "Providencia"}],
            "links": [{"kind": "instagram", "url": "https://instagram.com/nueva"}],
            "styles": [{"slug": "salsa-cubana", "confidence": 0.9}],
        },
        evidence={},
        confidence=0.9,
    )
    aid = approve(conn, pid)
    row = conn.execute(
        "select verified_at from academies where id = %s", (aid,)
    ).fetchone()
    assert row["verified_at"] is not None
    styles = conn.execute(
        """
        select s.slug from academy_styles a
        join styles s on s.id = a.style_id
        where a.academy_id = %s
        """,
        (aid,),
    ).fetchall()
    assert [r["slug"] for r in styles] == ["salsa-cubana"]


def test_approve_create_accepts_social_only_academy(conn):
    cand = Candidate("Academia Solo IG", "https://instagram.com/soloig2", "soloig2", "serpapi")
    cid = upsert_candidate(conn, cand)
    pid = insert_proposal(
        conn,
        candidate_id=cid,
        academy_id=None,
        kind="create",
        payload={
            "name": "Academia Solo IG",
            "links": [
                {"kind": "instagram", "url": "https://instagram.com/soloig2"}
            ],
        },
        evidence={},
        confidence=1.0,
    )
    aid = approve(conn, pid)

    locations = conn.execute(
        "select count(*) from academy_locations where academy_id = %s", (aid,)
    ).fetchone()
    assert locations["count"] == 0
    links = conn.execute(
        "select kind, url from academy_links where academy_id = %s", (aid,)
    ).fetchall()
    assert [(row["kind"], row["url"]) for row in links] == [
        ("instagram", "https://instagram.com/soloig2")
    ]


def test_approve_edit_records_rejection(conn):
    cand = Candidate("Academia Edit", "https://edit.cl", None, "seed")
    cid = upsert_candidate(conn, cand)
    pid = insert_proposal(
        conn,
        candidate_id=cid,
        academy_id=None,
        kind="create",
        payload={"name": "Academia Edit", "locations": [{"address": "Mala 1"}]},
        evidence={},
        confidence=0.9,
    )
    aid = approve(
        conn,
        pid,
        payload={"name": "Academia Edit", "locations": [{"address": "Buena 2"}]},
    )
    assert (
        "address",
        field_value_hash("address", "Mala 1"),
    ) in rejected_values(conn, aid)


def test_reject_marks_proposal(conn):
    cand = Candidate("Academia Rechazo", "https://rechazo.cl", None, "seed")
    cid = upsert_candidate(conn, cand)
    pid = insert_proposal(
        conn,
        candidate_id=cid,
        academy_id=None,
        kind="create",
        payload={"name": "Academia Rechazo"},
        evidence={},
        confidence=0.5,
    )
    reject(conn, pid)
    row = conn.execute(
        "select status from proposals where id = %s", (pid,)
    ).fetchone()
    assert row["status"] == "rejected"
