from types import SimpleNamespace

from bailoteca.geocode import USER_AGENT, GeocodePlan, nominatim_search, run


class _Response:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = data or []

    def json(self):
        return self._data


class _Client:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params, headers))
        return self.responses.pop(0)


class _Conn:
    def __init__(self, rows):
        self.rows = rows
        self.updates = []

    def execute(self, sql, params=()):
        if sql.strip().startswith("update"):
            self.updates.append((sql, tuple(params)))
            return SimpleNamespace(rowcount=1)
        return SimpleNamespace(fetchall=lambda: self.rows)


def _row(**overrides):
    base = {"location_id": "l1", "academy_slug": "sala", "address": "Calle 1",
            "comuna": "Santiago", "sede_count": 1,
            "google_lat": None, "google_lng": None}
    return {**base, **overrides}


def test_nominatim_sends_identifying_user_agent():
    client = _Client([_Response(data=[{"lat": "-33.45", "lon": "-70.66"}])])
    assert nominatim_search("Calle 1, Santiago, Chile", client) == (-33.45, -70.66)
    _, params, headers = client.calls[0]
    assert params["countrycodes"] == "cl" and params["format"] == "jsonv2"
    assert headers["User-Agent"] == USER_AGENT


def test_nominatim_failures_return_none():
    assert nominatim_search("x", _Client([_Response(status_code=500)])) is None
    assert nominatim_search("x", _Client([_Response(data=[])])) is None


def test_single_sede_inherits_google_without_http():
    client = _Client([])
    result = run(_Conn([_row(google_lat=-33.4, google_lng=-70.6)]), client)
    assert result == [GeocodePlan("l1", "sala", "Calle 1", -33.4, -70.6, "google", None)]
    assert client.calls == []


def test_multi_sede_does_not_inherit_google():
    result = run(_Conn([_row(address=None, sede_count=2, google_lat=-33.4)]), _Client([]))
    assert result[0].source is None and result[0].reason == "sin dirección"


def test_comuna_only_is_skipped_without_http():
    client = _Client([])
    result = run(_Conn([_row(address=None)]), client)
    assert result[0].reason == "sin dirección" and client.calls == []


def test_falls_back_to_nominatim_with_delay():
    # segunda sede sin número de calle: el fallback google_embed exige número, así que
    # queda intacto el camino "Nominatim miss → sin resultado" que este test fija
    rows = [_row(), _row(location_id="l2", academy_slug="b", address="Calle Sin Número")]
    client = _Client([
        _Response(data=[{"lat": "-33.45", "lon": "-70.66"}]),
        _Response(data=[]),
    ])
    sleeps = []

    result = run(_Conn(rows), client, apply=True, sleep=sleeps.append)

    assert (result[0].source, result[0].lat) == ("nominatim", -33.45)
    assert result[1].reason == "sin resultado"
    assert sleeps == [1.1] and len(client.calls) == 2


def test_dry_run_does_not_write():
    conn = _Conn([_row(google_lat=-33.4, google_lng=-70.6)])
    run(conn, _Client([]), apply=False)
    assert conn.updates == []


def test_piso_segmento_is_stripped_from_nominatim_query():
    rows = [_row(address="San Antonio 580, Piso 11, Santiago Centro")]
    client = _Client([_Response(data=[{"lat": "-33.43", "lon": "-70.64"}])])

    result = run(_Conn(rows), client, sleep=lambda s: None)

    _, params, _ = client.calls[0]
    assert "Piso" not in params["q"]
    assert params["q"].startswith("San Antonio 580")
    assert "Santiago Centro" in params["q"]
    assert result[0].source == "nominatim"


def test_oficina_and_depto_segments_are_stripped():
    rows = [_row(address="Av. Siempre Viva 100, Oficina 402")]
    client = _Client([_Response(data=[{"lat": "-33.45", "lon": "-70.66"}])])

    result = run(_Conn(rows), client, sleep=lambda s: None)

    _, params, _ = client.calls[0]
    assert "Oficina" not in params["q"] and "402" not in params["q"]
    assert result[0].source == "nominatim"


def test_address_without_piso_is_unchanged():
    rows = [_row(address="Calle 1")]
    client = _Client([_Response(data=[{"lat": "-33.45", "lon": "-70.66"}])])

    run(_Conn(rows), client, sleep=lambda s: None)

    _, params, _ = client.calls[0]
    assert params["q"] == "Calle 1, Santiago, Chile"


from pathlib import Path

from bailoteca import google_embed


def _embed_ok():
    return Path(__file__).parent / "fixtures" / "embed_place.html"


class _TextResponse(_Response):
    def __init__(self, html):
        super().__init__(status_code=200, data=None)
        self._html = html

    def json(self):  # embed responses are not JSON
        raise ValueError("not json")

    @property
    def text(self):
        return self._html


def test_nominatim_miss_falls_back_to_google_embed():
    html = _embed_ok().read_text()
    client = _Client([_Response(data=[]), _TextResponse(html)])
    rows = [_row(address="Gran Avenida 5608, San Miguel", comuna="San Miguel")]
    conn = _Conn(rows)

    result = run(conn, client, apply=True, sleep=lambda s: None)

    assert result[0].source == "google_embed" and round(result[0].lat, 4) == -33.5053
    sql, params = conn.updates[0]
    assert "coords_source" in sql
    assert params[2] == "google_embed"  # orden (lat, lng, coords_source, id)


def test_embed_query_includes_comuna():
    html = _embed_ok().read_text()
    client = _Client([_Response(data=[]), _TextResponse(html)])

    run(_Conn([_row(address="Gran Avenida 5608, San Miguel", comuna="San Miguel")]),
        client, sleep=lambda s: None)

    _, params, _ = client.calls[1]
    assert "San Miguel" in params["q"]


def test_embed_gate_rejection_writes_nothing():
    html = (Path(__file__).parent / "fixtures" / "embed_casa_cultura.html").read_text()
    client = _Client([_Response(data=[]), _TextResponse(html)])
    rows = [_row(address="Lucerna 64, La Cisterna", comuna="La Cisterna")]
    conn = _Conn(rows)

    result = run(conn, client, apply=True, sleep=lambda s: None)

    assert result[0].source is None and "google-embed" in (result[0].reason or "")
    assert conn.updates == []


def test_embed_parse_failure_writes_nothing():
    client = _Client([_Response(data=[]), _TextResponse("<html>no embed</html>")])
    conn = _Conn([_row(address="Gran Avenida 5608, San Miguel")])

    result = run(conn, client, apply=True, sleep=lambda s: None)

    assert result[0].source is None and conn.updates == []


def test_embed_dry_run_writes_nothing():
    html = _embed_ok().read_text()
    client = _Client([_Response(data=[]), _TextResponse(html)])
    conn = _Conn([_row(address="Gran Avenida 5608, San Miguel")])

    result = run(conn, client, apply=False, sleep=lambda s: None)

    assert result[0].source == "google_embed" and conn.updates == []
