from bailoteca.config import Config
from bailoteca.enrich import Page
from bailoteca.models import Candidate
from bailoteca.run import parse_add_target, run


class _Source:
    name = "fake"

    def discover(self):
        return [Candidate("Academia Dry", "https://dry.cl", None, "fake")]


class _Fetcher:
    def get(self, url):
        return Page(
            url,
            200,
            "<html><meta name='description' content='Salsa cubana'></html>",
            "Salsa cubana",
        )


def test_parse_add_target():
    assert parse_add_target("@academia_x").handle == "academia_x"
    assert parse_add_target("Academia X").name == "Academia X"
    assert parse_add_target("https://academia.cl").url == "https://academia.cl"


def test_run_dry_run_writes_reports(tmp_path):
    summary = run(
        Config.from_env(
            {"BAILOTECA_REPORTS_DIR": str(tmp_path), "BAILOTECA_SOURCES": "fake"}
        ),
        dry_run=True,
        sources=[_Source()],
        fetcher=_Fetcher(),
        llm=None,
    )
    assert summary.discovered == 1
    day = next(p for p in tmp_path.iterdir() if p.is_dir())
    assert (day / "candidates.json").exists()
    assert (day / "proposals.json").exists()


def test_run_skips_already_published_academy(tmp_path, monkeypatch):
    import os
    import uuid

    import pytest

    from bailoteca.db import connect, insert_proposal, upsert_candidate
    from bailoteca.publish import approve

    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")

    name = f"Academia Publicada {uuid.uuid4().hex[:8]}"
    candidate = Candidate(name, "https://publicada.cl", None, "seed")

    conn = connect(url)
    try:
        candidate_id = upsert_candidate(conn, candidate)
        proposal_id = insert_proposal(
            conn,
            candidate_id=candidate_id,
            academy_id=None,
            kind="create",
            payload={
                "name": name,
                "styles": [{"slug": "salsa-cubana", "confidence": 0.9}],
            },
            evidence={},
            confidence=0.9,
        )
        academy_id = approve(conn, proposal_id)
        conn.commit()

        class _CountingFetcher:
            calls = 0

            def get(self, page_url):
                self.calls += 1
                return Page(page_url, 200, "", "")

        fetcher = _CountingFetcher()

        # Mock httpx used in check_published
        class _MockResponse:
            status_code = 200

        class _MockHttp:
            def head(self, link_url):
                return _MockResponse()

            def get(self, link_url):
                return _MockResponse()

        import httpx
        monkeypatch.setattr(httpx, "head", lambda *a, **k: _MockResponse())
        monkeypatch.setattr(httpx, "get", lambda *a, **k: _MockResponse())

        summary = run(
            Config.from_env(
                {"DANCE_REPORTS_DIR": str(tmp_path), "DATABASE_URL": url}
            ),
            dry_run=False,
            sources=[_Source2(candidate)],
            fetcher=fetcher,
            llm=None,
        )
        assert summary.proposals == 0
        assert fetcher.calls == 0
    finally:
        conn.execute("delete from academies where id = %s", (academy_id,))
        conn.execute("delete from candidates where id = %s", (candidate_id,))
        conn.commit()
        conn.close()


class _Source2:
    name = "fake"

    def __init__(self, candidate):
        self.candidate = candidate

    def discover(self):
        return [self.candidate]


def _fake_triage(accepted: bool):
    class _Triage:
        def evaluate(self, candidate, enriched):
            from bailoteca.clef import Triage

            return Triage(accepted=accepted, score=0.9 if accepted else 0.1)

    return _Triage()


def test_run_drops_candidate_rejected_by_clef(tmp_path):
    summary = run(
        Config.from_env({"BAILOTECA_REPORTS_DIR": str(tmp_path)}),
        dry_run=True,
        sources=[_Source()],
        fetcher=_Fetcher(),
        llm=None,
        triage=_fake_triage(False),
    )
    assert summary.discovered == 1
    assert summary.filtered_clef == 1
    assert summary.proposals == 0


def test_run_keeps_candidate_on_clef_error(tmp_path):
    class _ErrTriage:
        def evaluate(self, candidate, enriched):
            from bailoteca.clef import Triage

            return Triage(accepted=True, score=None, error="timeout")

    summary = run(
        Config.from_env({"BAILOTECA_REPORTS_DIR": str(tmp_path)}),
        dry_run=True,
        sources=[_Source()],
        fetcher=_Fetcher(),
        llm=None,
        triage=_ErrTriage(),
    )
    assert summary.clef_errors == 1
    assert summary.filtered_clef == 0
    assert summary.proposals == 1


def test_run_applies_gemini_identity_normalization(tmp_path):
    from bailoteca.llm import StyleHit

    class _LLM:
        def __init__(self):
            self.calls = 0

        def classify_styles(self, text, slugs):
            return [StyleHit("salsa-cubana", 0.9)]

        def normalize_identity(self, text, fallback_name):
            self.calls += 1
            return "Clean Name Academy"

    summary = run(
        Config.from_env(
            {"BAILOTECA_REPORTS_DIR": str(tmp_path), "BAILOTECA_SOURCES": "fake"}
        ),
        dry_run=True,
        sources=[_Source()],
        fetcher=_Fetcher(),
        llm=_LLM(),
    )
    assert summary.proposals == 1
    day = next(p for p in tmp_path.iterdir() if p.is_dir())
    candidates = (day / "candidates.json").read_text()
    assert '"name": "Clean Name Academy"' in candidates
    assert '"name": "Academia Dry"' not in candidates
