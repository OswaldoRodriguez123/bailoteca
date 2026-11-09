from directorio_baile.discover import collect
from directorio_baile.models import Candidate


class FakeSource:
    def __init__(self, name, candidates):
        self.name = name
        self._candidates = candidates

    def discover(self):
        return self._candidates


def test_collect_dedupes_same_candidate_from_two_sources():
    a = Candidate("Academia X", "https://www.academia-x.cl/", None, "seed")
    b = Candidate("academia x", "http://academia-x.cl", None, "ddg")
    result = collect([FakeSource("seed", [a]), FakeSource("ddg", [b])])
    assert len(result) == 1
