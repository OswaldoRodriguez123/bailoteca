from directorio_baile.links import check_link


class _Response:
    def __init__(self, status):
        self.status_code = status


class _Http:
    def __init__(self, statuses):
        self.statuses = iter(statuses)

    def head(self, url):
        return _Response(next(self.statuses))

    def get(self, url):
        return _Response(next(self.statuses))


def test_ok_dead_blocked_unknown():
    assert check_link("https://ok.cl", _Http([200])) == "ok"
    assert check_link("https://dead.cl", _Http([404])) == "dead"
    assert check_link("https://blocked.cl", _Http([403])) == "blocked"
    assert check_link("https://unknown.cl", _Http([500])) == "unknown"


def test_head_405_falls_back_to_get():
    assert check_link("https://ok.cl", _Http([405, 200])) == "ok"
