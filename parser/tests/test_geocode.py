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
    rows = [_row(), _row(location_id="l2", academy_slug="b", address="Calle 2")]
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
