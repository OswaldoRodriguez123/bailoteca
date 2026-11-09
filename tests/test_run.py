from directorio_baile.config import Config
from directorio_baile.enrich import Page
from directorio_baile.models import Candidate
from directorio_baile.run import parse_add_target, run


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
            {"DANCE_REPORTS_DIR": str(tmp_path), "DANCE_SOURCES": "fake"}
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
