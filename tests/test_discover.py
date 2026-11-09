from bailoteca.discover import collect
from bailoteca.models import Candidate


class FakeSource:
    def __init__(self, name, candidates):
        self.name = name
        self._candidates = candidates

    def discover(self):
        return self._candidates


def test_collect_dedupes_same_candidate_from_two_sources():
    a = Candidate("Academia X", "https://www.academia-x.cl/", None, "seed")
    b = Candidate("academia x", "http://academia-x.cl", None, "ddg")
    result = collect([FakeSource("seed", [a]), FakeSource("ddg", [b])]).candidates
    assert len(result) == 1


def test_collect_merges_missing_url_and_handle():
    a = Candidate("Academia Y", None, None, "seed")
    b = Candidate("Academia Y", "https://y.cl", "y", "ddg")
    result = collect([FakeSource("seed", [a]), FakeSource("ddg", [b])]).candidates
    assert result[0].url == "https://y.cl"
    assert result[0].handle == "y"


def test_collect_applies_noise_rules_and_counts():
    from bailoteca.discover import CollectResult

    noise = Candidate("Directorio", "https://www.superprof.cl/salsa", None, "ddg")
    real = Candidate("Academia Z", "https://z.cl", None, "ddg")
    result = collect([FakeSource("ddg", [noise, real])])
    assert isinstance(result, CollectResult)
    assert [c.name for c in result.candidates] == ["Academia Z"]
    assert result.filtered_rules == 1
