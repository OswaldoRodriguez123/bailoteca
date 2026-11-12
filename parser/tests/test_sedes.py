from types import SimpleNamespace

from bailoteca.models import Candidate
from bailoteca.sedes import (
    _sede_from_text,
    build_pass_a_prompt,
    comuna_from_text,
    extract_rm_comuna,
    looks_chilean,
    parse_llm_json,
    pass_a,
    pass_b,
    run,
)

ARTFIT = {
    "id": "11111111-1111-1111-1111-111111111111",
    "slug": "artfit",
    "name": "artfit",
    "description": "Academia de baile latino",
    "source_urls": ["https://artfit.cl/web", "https://instagram.com/artfit"],
    "google": None,
}

SALA_MARINA = {
    "id": "22222222-2222-2222-2222-222222222222",
    "slug": "sala-marina",
    "name": "Sala Marina",
    "description": "Escuela de baile flamenco en Santiago",
    "source_urls": ["https://salamarina.es"],
    "google": {"address": "Carretera de Madrid s/n, Polinyà de Xúquer, España"},
}


class FakeLLM:
    """Devuelve respuestas encoladas; registra los prompts recibidos."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts: list[str] = []

    def extract(self, prompt):
        self.prompts.append(prompt)
        if not self.responses:
            return None
        return self.responses.pop(0)


class FakeBrave:
    def __init__(self, candidates):
        self._candidates = list(candidates)
        self.calls = 0

    def discover(self):
        self.calls += 1
        return list(self._candidates)


class _FakeConn:
    """Conexión falsa: select devuelve dicts; los inserts se capturan."""

    def __init__(self, rows):
        self._rows = list(rows)
        self.inserts: list[tuple] = []
        self.commits = 0
        self.queries: list[str] = []

    def execute(self, sql, params=None):
        normalized = sql.strip().lower()
        self.queries.append(sql)
        if normalized.startswith("select"):
            return SimpleNamespace(fetchall=lambda: list(self._rows))
        if normalized.startswith("insert into academy_locations"):
            self.inserts.append(params)
            return SimpleNamespace(rowcount=1)
        raise AssertionError(f"unexpected SQL {sql}")

    def commit(self):
        self.commits += 1

    def close(self):
        pass


def _candidate(name, url, description=None):
    raw = {"description": description} if description else {}
    return Candidate(name=name, url=url, handle=None, source="brave", raw=raw)


# --- compuerta extract_rm_comuna ---


def test_extract_rm_comuna_exactas():
    assert extract_rm_comuna("Providencia") == "Providencia"
    assert extract_rm_comuna("estación central") == "Estación Central"
    assert extract_rm_comuna("San José de Maipo") == "San José de Maipo"
    assert extract_rm_comuna("nunoa") == "Ñuñoa"


def test_extract_rm_comuna_rechaza_abreviaturas():
    assert extract_rm_comuna("est. central") is None


def test_extract_rm_comuna_rechaza_no_rm():
    assert extract_rm_comuna("Antofagasta") is None


def test_extract_rm_comuna_rechaza_vacios():
    assert extract_rm_comuna(None) is None
    assert extract_rm_comuna("") is None
    assert extract_rm_comuna("   ") is None


# --- looks_chilean ---


def test_looks_chilean_true():
    assert (
        looks_chilean("Av. Ricardo Cumming 78, 8350598 Santiago, Región Metropolitana")
        is True
    )


def test_looks_chilean_false():
    assert (
        looks_chilean("Carretera de Madrid s/n, Polinyà de Xúquer, España") is False
    )


# --- parse_llm_json ---


def test_parse_llm_json_tolera_fences():
    assert parse_llm_json('```json\n{"comuna": "Providencia"}\n```') == {
        "comuna": "Providencia"
    }
    assert parse_llm_json("null") is None
    assert parse_llm_json("no json") is None
    assert parse_llm_json('texto previo {"comuna": "Ñuñoa"} texto') == {
        "comuna": "Ñuñoa"
    }


# --- Pasada A ---


def test_pass_a_asigna_sede_y_usa_source_urls_primero():
    llm = FakeLLM([{"comuna": "Estación Central", "address": "Radal 189"}])

    sede = pass_a(ARTFIT, llm)

    assert sede is not None
    assert sede["comuna"] == "Estación Central"
    assert sede["address"] == "Radal 189"
    assert sede["source_url"] == ARTFIT["source_urls"][0]


def test_pass_a_comuna_no_rm_no_asigna_sede():
    llm = FakeLLM([{"comuna": "Antofagasta", "address": "Av. Grecia 123"}])

    assert pass_a(ARTFIT, llm) is None


def test_pass_a_prompt_omite_google_no_chileno():
    llm = FakeLLM([{"comuna": "Providencia", "address": "Av. Providencia 1234"}])

    sede = pass_a(SALA_MARINA, llm)

    prompt = llm.prompts[0]
    assert "Polinyà de Xúquer" not in prompt
    assert "Carretera de Madrid" not in prompt
    # Si el LLM responde Santiago desde la descripción, se acepta.
    assert sede is not None
    assert sede["comuna"] == "Providencia"


def test_pass_a_prompt_incluye_google_chileno():
    academy = dict(
        ARTFIT,
        google={"address": "Av. Ricardo Cumming 78, 8350598 Santiago, Región Metropolitana"},
    )
    llm = FakeLLM([{"comuna": "Santiago", "address": "Av. Ricardo Cumming 78"}])

    pass_a(academy, llm)

    assert "Ricardo Cumming" in llm.prompts[0]


# --- Pasada B ---


def test_pass_b_usa_primer_candidato_que_pasa_el_gate():
    candidates = [
        _candidate("resultado 1", "https://uno.cl/", "sucursal en Providencia"),
        _candidate("resultado 2", "https://dos.cl/", "también Providencia"),
        _candidate("resultado 3", "https://tres.cl/", "Providencia"),
    ]
    brave = FakeBrave(candidates)
    llm = FakeLLM([{"comuna": "Providencia", "address": "Av. Providencia 1234"}])

    sede = pass_b(ARTFIT, brave, llm)

    assert sede is not None
    assert sede["comuna"] == "Providencia"
    assert sede["source_url"] == candidates[0].url


def test_pass_b_salta_candidatos_que_fallan_el_gate():
    candidates = [
        _candidate("resultado 1", "https://uno.cl/", "academia en Antofagasta"),
        _candidate("resultado 2", "https://dos.cl/", "academia en Providencia"),
    ]
    brave = FakeBrave(candidates)
    llm = FakeLLM(
        [
            {"comuna": "Antofagasta", "address": "Av. Grecia 123"},
            {"comuna": "Providencia", "address": "Av. Providencia 1234"},
        ]
    )

    sede = pass_b(ARTFIT, brave, llm)

    assert sede is not None
    assert sede["source_url"] == candidates[1].url


def test_pass_b_snippets_vacios_devuelve_none():
    # Sin nombre NI descripción no hay evidencia: el candidato se omite y
    # el LLM no se llama.
    brave = FakeBrave([Candidate(name="", url="https://uno.cl/", handle=None, source="brave", raw={})])
    llm = FakeLLM([])

    assert pass_b(ARTFIT, brave, llm) is None
    assert llm.prompts == []


def test_pass_b_candidato_con_titulo_sin_descripcion_llega_al_llm():
    # Major 1: un título sin descripción igual se consulta al LLM.
    candidate = _candidate("Academia Solo Nombre", "https://solo.cl/")
    brave = FakeBrave([candidate])
    llm = FakeLLM([{"comuna": "Providencia", "address": "Av. Providencia 1234"}])

    sede = pass_b(ARTFIT, brave, llm)

    assert sede is not None
    assert sede["source_url"] == "https://solo.cl/"
    assert len(llm.prompts) == 1
    assert "Academia Solo Nombre" in llm.prompts[0]


def test_pass_b_sin_resultados_devuelve_none():
    brave = FakeBrave([])
    llm = FakeLLM([])

    assert pass_b(ARTFIT, brave, llm) is None


# --- run (dry-run / apply) ---


def test_run_apply_sede_sin_fuente_se_omite_no_con_sede(capsys):
    # Major 2: sede detectada sin source_url no cuenta como con_sede y no se inserta.
    academy = dict(
        ARTFIT,
        id="33333333-3333-3333-3333-333333333333",
        slug="sin-fuente",
        source_urls=[],
    )
    conn = _FakeConn([academy])

    def brave_factory(query):
        return FakeBrave([])

    llm = FakeLLM([{"comuna": "Providencia", "address": "Av. Providencia 1234"}])

    assert run(conn, llm=llm, brave_factory=brave_factory, apply=True) == 0

    assert conn.inserts == []
    out = capsys.readouterr().out
    assert "con_sede=0" in out
    assert "omitidas_sin_fuente=1" in out
    assert "insertadas=0" in out
    # La tabla la marca como no insertada.
    assert "SIN FUENTE" in out


def test_run_query_selecciona_no_cerradas():
    # Producción: todas las filas tienen status='unknown' (nunca mantenido);
    # publication is verified_at and the API lists regardless of status.
    # El selector solo debe excluir 'closed'.
    conn = _FakeConn([ARTFIT])

    def brave_factory(query):
        return FakeBrave([])

    llm = FakeLLM([None])

    assert run(conn, llm=llm, brave_factory=brave_factory, apply=False) == 0

    sql = " ".join(conn.queries).lower()
    assert "<> 'closed'" in sql
    assert "status='active'" not in sql
    assert "order by a.slug" in sql


def test_run_dry_run_no_inserta(capsys):
    conn = _FakeConn([ARTFIT, SALA_MARINA])

    def brave_factory(query):
        return FakeBrave([])

    llm = FakeLLM(
        [
            {"comuna": "Estación Central", "address": "Radal 189"},  # Pasada A artfit
            None,  # Pasada A sala-marina (el LLM no sabe)
        ]
    )

    assert run(conn, llm=llm, brave_factory=brave_factory, apply=False) == 0

    assert conn.inserts == []
    assert conn.commits == 0
    out = capsys.readouterr().out
    assert "total=2" in out
    assert "con_sede=1" in out


def test_run_apply_inserta_solo_las_que_pasan_el_gate():
    conn = _FakeConn([ARTFIT, SALA_MARINA])

    def brave_factory(query):
        return FakeBrave([])

    llm = FakeLLM(
        [
            {"comuna": "Estación Central", "address": "Radal 189"},  # Pasada A artfit
            None,  # Pasada A sala-marina
        ]
    )

    assert run(conn, llm=llm, brave_factory=brave_factory, apply=True) == 0

    assert conn.commits == 1
    assert len(conn.inserts) == 1
    params = conn.inserts[0]
    assert params[0] == ARTFIT["id"]
    assert params[1] == "Sede"
    assert params[2] == "Radal 189"
    assert params[3] == "Estación Central"
    assert params[4] is None and params[5] is None  # lat/lng null
    assert params[6] == "metropolitana"
    assert params[7] == ARTFIT["source_urls"][0]


def test_run_pasada_a_no_rm_cae_en_pasada_b(capsys):
    conn = _FakeConn([ARTFIT])
    factory_queries: list[str] = []

    def brave_factory(query):
        factory_queries.append(query)
        return FakeBrave([])

    llm = FakeLLM([{"comuna": "Antofagasta", "address": "Av. Grecia 123"}])

    assert run(conn, llm=llm, brave_factory=brave_factory, apply=False) == 0

    assert factory_queries == ['"artfit" Santiago comuna']
    out = capsys.readouterr().out
    assert "con_sede=0" in out


def test_run_apply_inserta_via_pasada_b_con_source_url_brave():
    conn = _FakeConn([ARTFIT])
    candidate = _candidate("artfit en providencia", "https://brave-hit.cl/", "sede en Providencia")

    def brave_factory(query):
        return FakeBrave([candidate])

    llm = FakeLLM(
        [
            {"comuna": "Antofagasta", "address": "Av. Grecia 123"},  # Pasada A falla gate
            {"comuna": "Providencia", "address": "Av. Providencia 1234"},  # Pasada B
        ]
    )

    assert run(conn, llm=llm, brave_factory=brave_factory, apply=True) == 0

    assert len(conn.inserts) == 1
    assert conn.inserts[0][6] == "metropolitana"
    assert conn.inserts[0][7] == "https://brave-hit.cl/"


def test_run_sin_sede_cuando_todo_falla(capsys):
    conn = _FakeConn([ARTFIT])

    def brave_factory(query):
        return FakeBrave(
            [_candidate("resultado", "https://uno.cl/", "academia en Antofagasta")]
        )

    llm = FakeLLM(
        [
            {"comuna": "Antofagasta", "address": "Av. Grecia 123"},  # A: no-RM
            {"comuna": "Antofagasta", "address": "Av. Grecia 123"},  # B: no-RM
        ]
    )

    assert run(conn, llm=llm, brave_factory=brave_factory, apply=False) == 0

    out = capsys.readouterr().out
    assert "con_sede=0" in out
    assert "AMBIGUA" in out


def test_pass_a_fallback_fuente_prioriza_web_sobre_instagram():
    academy = dict(
        ARTFIT,
        source_urls=[],
        links=[
            {"kind": "instagram", "url": "https://instagram.com/artfit"},
            {"kind": "web", "url": "https://artfit.cl"},
        ],
    )
    llm = FakeLLM([{"comuna": "Estación Central", "address": "Radal 189"}])

    sede = pass_a(academy, llm)

    assert sede is not None
    assert sede["source_url"] == "https://artfit.cl"


def test_pass_a_fallback_fuente_prioriza_orden_completo():
    # web > facebook > instagram > tiktok > youtube > other
    academy = dict(
        ARTFIT,
        source_urls=[],
        links=[
            {"kind": "other", "url": "https://otro.cl/"},
            {"kind": "instagram", "url": "https://instagram.com/artfit"},
            {"kind": "facebook", "url": "https://facebook.com/artfit"},
        ],
    )
    llm = FakeLLM([{"comuna": "Estación Central", "address": "Radal 189"}])

    assert pass_a(academy, llm)["source_url"] == "https://facebook.com/artfit"


def test_pass_a_fallback_excluye_email_phone_whatsapp_y_prefijos():
    academy = dict(
        ARTFIT,
        source_urls=[],
        links=[
            {"kind": "whatsapp", "url": "https://wa.me/56912345678"},
            {"kind": "email", "url": "mailto:hola@artfit.cl"},
            {"kind": "phone", "url": "tel:+56912345678"},
            {"kind": "web", "url": "https://wa.me/56999999999"},  # prefijo wa.me excluido aun como web
        ],
    )
    llm = FakeLLM([{"comuna": "Providencia", "address": "Av. X 1"}])

    assert pass_a(academy, llm)["source_url"] is None


def test_pass_a_fallback_no_se_usa_si_hay_source_urls():
    academy = dict(
        ARTFIT,
        source_urls=["https://primary.cl/"],
        links=[{"kind": "web", "url": "https://artfit.cl"}],
    )
    llm = FakeLLM([{"comuna": "Estación Central", "address": "Radal 189"}])

    assert pass_a(academy, llm)["source_url"] == "https://primary.cl/"


def test_run_apply_sin_fuente_ni_link_usable_queda_omitida(capsys):
    academy = dict(
        ARTFIT,
        id="44444444-4444-4444-4444-444444444444",
        slug="sin-links",
        source_urls=[],
        links=[
            {"kind": "whatsapp", "url": "https://wa.me/56912345678"},
            {"kind": "email", "url": "mailto:hola@artfit.cl"},
        ],
    )
    conn = _FakeConn([academy])

    def brave_factory(query):
        return FakeBrave([])

    llm = FakeLLM([{"comuna": "Providencia", "address": "Av. Providencia 1234"}])

    assert run(conn, llm=llm, brave_factory=brave_factory, apply=True) == 0

    assert conn.inserts == []
    out = capsys.readouterr().out
    assert "con_sede=0" in out
    assert "omitidas_sin_fuente=1" in out
    assert "insertadas=0" in out


def test_run_apply_inserta_con_fuente_fallback_de_links():
    academy = dict(
        ARTFIT,
        id="55555555-5555-5555-5555-555555555555",
        slug="con-links",
        source_urls=[],
        links=[{"kind": "instagram", "url": "https://instagram.com/artfit"}],
    )
    conn = _FakeConn([academy])

    def brave_factory(query):
        return FakeBrave([])

    llm = FakeLLM([{"comuna": "Providencia", "address": "Av. Providencia 1234"}])

    assert run(conn, llm=llm, brave_factory=brave_factory, apply=True) == 0

    assert len(conn.inserts) == 1
    assert conn.inserts[0][7] == "https://instagram.com/artfit"


def test_build_pass_a_prompt_no_incluye_google_no_chileno():
    prompt = build_pass_a_prompt(SALA_MARINA)

    assert "Polinyà de Xúquer" not in prompt
    assert "Carretera de Madrid" not in prompt


def test_build_pass_a_prompt_exige_lista_rm_y_null():
    prompt = build_pass_a_prompt(ARTFIT)

    assert "Providencia" in prompt
    assert "Estación Central" in prompt
    assert "null" in prompt
    assert "artfit" in prompt


# --- pre-paso determinista comuna_from_text ---


def test_comuna_from_text_estacion_central_gana_a_santiago():
    assert comuna_from_text("Radal 189, Estación Central, Santiago") == "Estación Central"


def test_comuna_from_text_providencia_santiago():
    assert comuna_from_text("Providencia, Santiago") == "Providencia"


def test_comuna_from_text_la_florida_santiago():
    assert comuna_from_text("La Florida, Santiago") == "La Florida"


def test_comuna_from_text_san_antonio_es_santiago():
    assert comuna_from_text("San Antonio 580, Piso 11, Santiago Centro") == "Santiago"


def test_comuna_from_text_excepcion_santiago_primero_devuelve_otro():
    assert comuna_from_text("Santiago, Estación Central") == "Estación Central"


def test_comuna_from_text_ambiguo_devuelve_none():
    assert comuna_from_text("Clases en Providencia y Ñuñoa") is None
    assert comuna_from_text("Santiago, Providencia y Ñuñoa") is None


def test_comuna_from_text_sin_comuna_devuelve_none():
    assert comuna_from_text("Academia de baile moderno") is None
    assert comuna_from_text("") is None


def test_comuna_from_text_limites_de_palabra():
    # "Las Condesas" no es "Las Condes" (límite de palabra real en texto normalizado)
    assert comuna_from_text("Las Condesas") is None


# --- pre-paso dentro de run() ---


def test_run_sala_marina_google_espana_sin_sede_y_llm_no_llamado(capsys):
    # La descripción dice Santiago, pero google.address es España: ni pre-paso
    # ni Gemini asignan sede.
    conn = _FakeConn([SALA_MARINA])  # descripción: "...en Santiago"

    def brave_factory(query):
        return FakeBrave([])

    llm = FakeLLM([{"comuna": "Providencia", "address": "Av. Providencia 1"}])

    assert run(conn, llm=llm, brave_factory=brave_factory, apply=False) == 0

    assert llm.prompts == []
    out = capsys.readouterr().out
    assert "con_sede=0" in out
    assert "sin_sede=1" in out


def test_run_prepass_texto_evita_llm_y_usa_fallback_de_links():
    academy = dict(
        ARTFIT,
        source_urls=[],
        links=[{"kind": "web", "url": "https://artfit.cl"}],
        description="Sede en Estación Central, Santiago",
    )
    conn = _FakeConn([academy])
    llm = FakeLLM([])  # el LLM no debe ser llamado

    assert run(conn, llm=llm, brave_factory=lambda q: FakeBrave([]), apply=True) == 0

    assert llm.prompts == []
    assert len(conn.inserts) == 1
    params = conn.inserts[0]
    assert params[3] == "Estación Central"
    assert params[6] == "metropolitana"
    assert params[7] == "https://artfit.cl"


def test_run_prepass_sin_link_usable_queda_omitida(capsys):
    academy = dict(
        ARTFIT,
        id="66666666-6666-6666-6666-666666666666",
        slug="sin-links-texto",
        source_urls=[],
        links=[
            {"kind": "whatsapp", "url": "https://wa.me/56912345678"},
            {"kind": "email", "url": "mailto:hola@artfit.cl"},
        ],
        description="Clases en Estación Central, Santiago",
    )
    conn = _FakeConn([academy])
    llm = FakeLLM([])

    assert run(conn, llm=llm, brave_factory=lambda q: FakeBrave([]), apply=True) == 0

    assert conn.inserts == []
    assert llm.prompts == []
    out = capsys.readouterr().out
    assert "con_sede=0" in out
    assert "omitidas_sin_fuente=1" in out


def test_run_prepass_direccion_es_la_oracion_con_la_comuna(capsys):
    academy = dict(
        ARTFIT,
        source_urls=[],
        links=[{"kind": "web", "url": "https://artfit.cl"}],
        description="Primero otro dato. Clases en Providencia desde 2010. Ultima frase.",
    )
    conn = _FakeConn([academy])
    llm = FakeLLM([])

    assert run(conn, llm=llm, brave_factory=lambda q: FakeBrave([]), apply=False) == 0

    out = capsys.readouterr().out
    assert "Clases en Providencia desde 2010" in out


def test_sede_from_text_direccion_truncada_a_200_y_via_texto():
    long_sentence = "Clases en Providencia " + "x" * 300
    academy = dict(
        ARTFIT,
        source_urls=[],
        links=[{"kind": "web", "url": "https://artfit.cl"}],
        description=long_sentence,
    )

    sede = _sede_from_text(academy)

    assert sede is not None
    assert len(sede["address"]) == 200
    assert sede["via"] == "texto"
    assert sede["comuna"] == "Providencia"


def test_run_prepass_evita_gemini_aunque_devolveria_otra_comuna():
    # Aunque Gemini dijera Antofagasta, el pre-paso es determinista y gana.
    academy = dict(
        ARTFIT,
        source_urls=[],
        links=[{"kind": "instagram", "url": "https://instagram.com/artfit"}],
        description="Sede en La Florida",
    )
    conn = _FakeConn([academy])
    llm = FakeLLM([{"comuna": "Antofagasta", "address": "Av. Grecia 123"}])

    assert run(conn, llm=llm, brave_factory=lambda q: FakeBrave([]), apply=True) == 0

    assert llm.prompts == []
    assert conn.inserts[0][3] == "La Florida"
