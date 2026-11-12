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


def test_collect_merges_pages_of_the_same_domain():
    a = Candidate(
        "Providencia - As You Wish",
        "https://asyouwish.cl/clases-de-baile-providencia/",
        None,
        "tinyfish",
    )
    b = Candidate(
        "Clases de Baile Ñuñoa Bachata - Salsa Cubana",
        "https://asyouwish.cl/clases-de-baile-nunoa/",
        None,
        "tinyfish",
    )
    result = collect([FakeSource("tinyfish", [a, b])]).candidates
    assert len(result) == 1
    assert result[0].name == "Providencia - As You Wish"
    assert result[0].url == "https://asyouwish.cl/clases-de-baile-providencia/"


def test_collect_merges_same_domain_across_sources_and_keeps_raw():
    a = Candidate(
        "As You Wish",
        "https://asyouwish.cl/",
        None,
        "brave",
        raw={"description": "clases de baile"},
    )
    b = Candidate(
        "Academia de Baile Ñuñoa | As You Wish",
        "https://www.asyouwish.cl/nunoa/",
        None,
        "tinyfish",
        raw={"description": "salsa y bachata"},
    )
    result = collect([FakeSource("brave", [a]), FakeSource("tinyfish", [b])]).candidates
    assert len(result) == 1
    assert result[0].source == "brave"
    assert result[0].raw == {"description": "salsa y bachata"}


def test_collect_keeps_multitenant_hosts_apart():
    a = Candidate("Academia A", "https://academiaa.wixsite.com/inicio", None, "brave")
    b = Candidate("Academia B", "https://academiab.wixsite.com/inicio", None, "tinyfish")
    result = collect([FakeSource("brave", [a]), FakeSource("tinyfish", [b])]).candidates
    assert len(result) == 2


def test_collect_keeps_instagram_profiles_apart():
    a = Candidate("Perfil A", "https://www.instagram.com/academiaa/", "academiaa", "brave")
    b = Candidate("Perfil B", "https://www.instagram.com/academiab/", "academiab", "tinyfish")
    result = collect([FakeSource("brave", [a]), FakeSource("tinyfish", [b])]).candidates
    assert len(result) == 2


def test_collect_keeps_subdomains_of_multitenant_hosts_apart():
    a = Candidate("Academia C", "https://sites.google.com/view/academiac/", None, "brave")
    b = Candidate("Academia D", "https://sites.google.com/view/academiad/", None, "tinyfish")
    result = collect([FakeSource("brave", [a]), FakeSource("tinyfish", [b])]).candidates
    assert len(result) == 2
