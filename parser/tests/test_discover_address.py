from types import SimpleNamespace

import pytest

from bailoteca.discover_address import classify, find_street, run


class _Response:
    def __init__(self, status_code=200, data=None, text=""):
        self.status_code = status_code
        self._data = data
        self.text = text

    def json(self):
        if self._data is None:
            raise ValueError("no json")
        return self._data


class _Client:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params, headers))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class _Conn:
    def __init__(self, rows):
        self.rows = rows
        self.updates = []
        self.selects = []

    def execute(self, sql, params=()):
        if sql.strip().lower().startswith("update"):
            self.updates.append((sql, tuple(params)))
            return SimpleNamespace(rowcount=1)
        self.selects.append(sql)
        return SimpleNamespace(fetchall=lambda: self.rows)


def _row(**overrides):
    base = {
        "location_id": "l1",
        "academy_slug": "sala",
        "academy_name": "Sala Ejemplo",
        "comuna": "Santiago",
        "own_urls": [],
    }
    return {**base, **overrides}


def _brave_json(entries):
    return {"web": {"results": entries}}


# --- find_street -----------------------------------------------------------

def test_find_street_accepts_common_formats():
    assert find_street("Av. Nueva Providencia 1705, Providencia") == "Av. Nueva Providencia 1705"
    assert find_street("Avenida Irarrázaval 4955 librería") == "Avenida Irarrázaval 4955"
    assert find_street("Calle 21 de Mayo 1234") == "Calle 21 de Mayo 1234"
    assert find_street("Camino El Alba 9500") == "Camino El Alba 9500"
    assert find_street("Psje. Los Robles 456") == "Psje. Los Robles 456"
    assert find_street("Diagonal Paraguay 1200") == "Diagonal Paraguay 1200"
    assert find_street("Avenida Libertador Bernardo O'Higgins 3456") is not None


def test_find_street_rejects_missing_number_or_prefix():
    assert find_street("Av. Providencia esquina con Pedro de Valdivia") is None
    assert find_street("Número 1705, Providencia") is None
    assert find_street("el 1705 está avisado") is None


# --- classify ---------------------------------------------------------------

def test_classify_own_domain_variants():
    own = ["https://misclasedebaile.cl/"]
    assert classify("https://misclasedebaile.cl/horario.php", None, own) is True
    assert classify("https://www.misclasedebaile.cl/x", None, own) is True
    assert classify("https://sub.danzaebano.cl/a", None, ["https://danzaebano.cl/x"]) is True
    assert classify("https://www.cylex.cl/nunoa/danza-ebano", None, ["https://danzaebano.cl/"]) is False
    assert classify(None, "Av. Nueva Providencia 1705", []) is False


# --- run -------------------------------------------------------------------

def test_dry_run_does_not_write():
    rows = [_row(own_urls=["https://mi.cl/"])]
    client = _Client([_Response(data=_brave_json([
        {"url": "https://mi.cl/contacto", "title": "Contacto",
         "description": "Dirección: Av. Ejemplo 123, Santiago"},
    ]))])
    proposals = run(_Conn(rows), client, "key", apply=False, sleep=lambda s: None)
    assert proposals[0].address == "Av. Ejemplo 123"
    assert proposals[0].source == "brave"
    assert proposals[0].own is True
    assert client.calls[0][0].startswith("https://api.search.brave.com")


def test_apply_writes_only_own():
    rows = [
        _row(location_id="loc-propia", academy_slug="propia", own_urls=["https://propia.cl/"]),
        _row(location_id="loc-terceros", academy_slug="terceros", own_urls=[]),
        _row(location_id="loc-web", academy_slug="web", own_urls=["https://web.cl/"]),
    ]
    client = _Client([
        _Response(data=_brave_json([
            {"url": "https://propia.cl/contacto", "title": "x",
             "description": "Av. Propia 111"},
        ])),
        _Response(data=_brave_json([
            {"url": "https://www.cylex.cl/terceros", "title": "x",
             "description": "Av. Terceros 222"},
        ])),
        _Response(data=_brave_json([])),
        _Response(text='<html><body><p>Calle Web 45, Santiago</p></body></html>'),
    ])
    conn = _Conn(rows)
    proposals = run(conn, client, "key", apply=True, sleep=lambda s: None)
    written = [(params[0], params[1]) for _, params in conn.updates]
    assert ("Av. Propia 111", "loc-propia") in written
    assert "Calle Web 45" in [p[0] for p in written]
    assert all("222" not in (p[0] or "") for p in written)
    by_slug = {p.academy_slug: p for p in proposals}
    assert by_slug["terceros"].own is False
    assert by_slug["web"].source == "web" and by_slug["web"].own is True


def test_brave_failure_falls_back_to_web_fetch():
    rows = [_row(own_urls=["https://caida.cl/"])]
    client = _Client([
        RuntimeError("brave caído"),
        _Response(text='<p>Camino El Alba 678</p>'),
    ])
    proposals = run(_Conn(rows), client, "key", apply=False, sleep=lambda s: None)
    assert proposals[0].address == "Camino El Alba 678"
    assert proposals[0].source == "web"


def test_no_results_reports_sin_hallazgo():
    rows = [_row(own_urls=[])]
    client = _Client([_Response(data=_brave_json([]))])
    proposals = run(_Conn(rows), client, "key", apply=False, sleep=lambda s: None)
    assert proposals[0].reason == "sin hallazgo"
    assert proposals[0].address is None


def test_rows_query_only_missing_address():
    conn = _Conn([])
    run(conn, _Client([]), "key", apply=False, sleep=lambda s: None)
    assert conn.selects, "no se ejecutó el SELECT"
    assert "address is null" in conn.selects[0].lower()
    assert "academy_links" in conn.selects[0].lower()


def test_malformed_brave_json_is_ignored():
    rows = [_row(own_urls=[])]
    client = _Client([_Response(data={"web": None})])
    proposals = run(_Conn(rows), client, "key", apply=False, sleep=lambda s: None)
    assert proposals[0].reason == "sin hallazgo"


def test_terceros_listing_without_own_yields_no_write_but_proposal():
    rows = [_row(own_urls=[])]
    client = _Client([_Response(data=_brave_json([
        {"url": "https://www.cylex.cl/x", "title": "x",
         "description": "Av. Cylex 123"},
    ]))])
    conn = _Conn(rows)
    proposals = run(conn, client, "key", apply=True, sleep=lambda s: None)
    assert proposals[0].own is False and proposals[0].address == "Av. Cylex 123"
    assert conn.updates == []
