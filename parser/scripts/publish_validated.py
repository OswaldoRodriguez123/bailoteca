"""Publica las academias validadas manualmente en la base.

Uso único: toma los 28 candidatos que pasaron el filtro de ruido, los cruza
con la caché local y publica las academias con datos verificables. No exige
página web: basta una red social (Instagram/Facebook) para aceptarlas.

Es idempotente: si la academia ya existe (mismo slug), actualiza sus datos en
lugar de crear un duplicado.
"""

from __future__ import annotations

import sys

from bailoteca.config import load
from bailoteca.db import (
    connect,
    insert_proposal,
    proposal_dedupe_key,
    upsert_candidate,
)
from bailoteca.models import Candidate
from bailoteca.normalize import domain_of, slugify
from bailoteca.publish import approve, reject, validate_payload

ACADEMIES: list[dict] = [
    {
        "name": "Dansón Academy",
        "description": (
            "Clases de salsa cubana (casino) en Santiago Centro, desde cero "
            "hasta nivel intermedio, sin pareja. También salsa en línea y "
            "mambo On2."
        ),
        "candidate_url": "https://danson.cl/clases-de-salsa-cubana",
        "locations": [
            {
                "label": "Santiago Centro",
                "address": "Santo Domingo 1277, oficina 203",
                "comuna": "Santiago",
                "source_url": "https://danson.cl/clases-de-salsa-cubana",
            }
        ],
        "links": [
            {"kind": "web", "url": "https://danson.cl/"},
            {"kind": "instagram", "url": "https://instagram.com/dansonacademy"},
            {"kind": "email", "url": "mailto:hola@danson.cl"},
            {"kind": "whatsapp", "url": "https://wa.me/56997440097"},
        ],
        "styles": [
            {
                "slug": "salsa-cubana",
                "confidence": 0.9,
                "evidence": "salsa cubana (casino)",
            },
            {
                "slug": "salsa-linea",
                "confidence": 0.9,
                "evidence": "clases de mambo y salsa en línea On2",
            },
            {"slug": "mambo", "confidence": 0.9, "evidence": "mambo On2"},
        ],
    },
    {
        "name": "Go Salsa",
        "description": (
            "Academia de salsa en Santiago Centro, a pasos del Metro Los "
            "Héroes. Clases desde cero y para quienes ya bailan."
        ),
        "candidate_url": "https://www.gosalsa.cl/",
        "locations": [
            {
                "label": "Santiago Centro",
                "address": "Av. Libertador Bernardo O'Higgins 1848, Piso 2",
                "comuna": "Santiago",
                "source_url": "https://www.gosalsa.cl/",
            }
        ],
        "links": [
            {"kind": "web", "url": "https://www.gosalsa.cl/"},
            {"kind": "instagram", "url": "https://instagram.com/academia.gosalsa"},
            {
                "kind": "facebook",
                "url": "https://facebook.com/AcademiaGoSalsaChile",
            },
            {"kind": "email", "url": "mailto:academia.gosalsa@gmail.com"},
        ],
        "styles": [],
    },
    {
        "name": "Mambo Madness",
        "description": (
            "Academia de salsa y mambo en Providencia. Clases y horarios de "
            "salsa en Santiago."
        ),
        "candidate_url": "https://www.salsasaborcaribe.com/book-online",
        "locations": [
            {
                "label": "Providencia",
                "address": "Almirante Riveros 0186",
                "comuna": "Providencia",
                "source_url": "https://www.salsasaborcaribe.com/",
            }
        ],
        "links": [
            {"kind": "web", "url": "https://www.salsasaborcaribe.com/"},
            {"kind": "instagram", "url": "https://instagram.com/mambo.madness"},
            {
                "kind": "email",
                "url": "mailto:mambomadnessdance@gmail.com",
            },
            {"kind": "phone", "url": "tel:+56962369351"},
        ],
        "styles": [
            {"slug": "mambo", "confidence": 0.9, "evidence": "Mambo Madness"}
        ],
    },
    {
        "name": "As You Wish",
        "description": (
            "Clases de baile en Providencia y Ñuñoa: salsa cubana, bachata y "
            "más."
        ),
        "candidate_url": "https://asyouwish.cl/clases-de-baile-nunoa/",
        "locations": [
            {
                "label": "Providencia",
                "comuna": "Providencia",
                "source_url": "https://asyouwish.cl/clases-de-baile-providencia/",
            },
            {
                "label": "Ñuñoa",
                "comuna": "Ñuñoa",
                "source_url": "https://asyouwish.cl/clases-de-baile-nunoa/",
            },
        ],
        "links": [
            {"kind": "web", "url": "https://asyouwish.cl/"},
            {"kind": "instagram", "url": "https://instagram.com/asyouwish.chile"},
            {"kind": "facebook", "url": "https://facebook.com/asyouwish.chile"},
            {"kind": "phone", "url": "tel:+56996791861"},
        ],
        "styles": [
            {
                "slug": "salsa-cubana",
                "confidence": 0.9,
                "evidence": "Salsa Cubana",
            }
        ],
    },
    {
        "name": "Sabor Latino Chile",
        "description": "Clases de salsa cubana y bachata en Puente Alto.",
        "candidate_url": "https://saborlatinochile.cl/",
        "locations": [
            {
                "label": "Puente Alto",
                "address": "Haití 3075",
                "comuna": "Puente Alto",
                "source_url": "https://saborlatinochile.cl/",
            }
        ],
        "links": [
            {"kind": "web", "url": "https://saborlatinochile.cl/"},
            {
                "kind": "instagram",
                "url": "https://instagram.com/saborlatinochile",
            },
            {
                "kind": "facebook",
                "url": "https://facebook.com/saborlatinochile",
            },
            {"kind": "whatsapp", "url": "https://wa.me/56981399063"},
            {"kind": "tiktok", "url": "https://tiktok.com/@saborlatinochile"},
        ],
        "styles": [
            {
                "slug": "salsa-cubana",
                "confidence": 0.9,
                "evidence": "Salsa cubana",
            }
        ],
    },
    {
        "name": "Bailemos Salsa",
        "description": (
            "Academia de salsa en Providencia y Ñuñoa: salsa casino, salsa "
            "On1, bachata y kizomba."
        ),
        "candidate_url": "https://bailemosalsa.cl/",
        "locations": [
            {
                "label": "Providencia",
                "address": "Seminario 130",
                "comuna": "Providencia",
                "source_url": "https://bailemosalsa.cl/",
            },
            {
                "label": "Ñuñoa",
                "address": "Av. Sucre 1840",
                "comuna": "Ñuñoa",
                "source_url": "https://bailemosalsa.cl/",
            },
        ],
        "links": [
            {"kind": "web", "url": "https://bailemosalsa.cl/"},
            {"kind": "instagram", "url": "https://instagram.com/bailemosalsa"},
            {"kind": "email", "url": "mailto:info@bailemosalsa.cl"},
            {"kind": "whatsapp", "url": "https://wa.me/56949529988"},
        ],
        "styles": [
            {
                "slug": "salsa-cubana",
                "confidence": 0.9,
                "evidence": "Salsa Casino",
            },
            {
                "slug": "salsa-linea",
                "confidence": 0.9,
                "evidence": "Salsa On1",
            },
        ],
    },
    {
        "name": "Abundanza",
        "description": (
            "Escuela de danza en Puente Alto: salsa, bachata, latin jazz y más."
        ),
        "candidate_url": "https://abundanza.ueniweb.com/",
        "locations": [
            {
                "label": "Puente Alto",
                "address": "Av. Concha Y Toro 3214",
                "comuna": "Puente Alto",
                "source_url": "https://abundanza.ueniweb.com/",
            }
        ],
        "links": [
            {"kind": "web", "url": "https://abundanza.ueniweb.com/"},
            {"kind": "instagram", "url": "https://instagram.com/abundanza33"},
            {"kind": "facebook", "url": "https://facebook.com/abundanza33"},
            {"kind": "phone", "url": "tel:+56979693695"},
        ],
        "styles": [],
    },
    {
        "name": "Mi Salsa",
        "description": (
            "Academia de baile en Maipú: salsa, rueda de casino, salsa en "
            "línea, bachata y más."
        ),
        "candidate_url": "https://www.misalsa.cl/",
        "locations": [
            {
                "label": "Maipú",
                "comuna": "Maipú",
                "source_url": "https://www.misalsa.cl/",
            }
        ],
        "links": [
            {"kind": "web", "url": "https://www.misalsa.cl/"},
            {
                "kind": "instagram",
                "url": "https://instagram.com/academiamisalsa",
            },
            {"kind": "phone", "url": "tel:+56956104555"},
        ],
        "styles": [
            {
                "slug": "salsa-cubana",
                "confidence": 0.65,
                "evidence": "Rueda de Casino",
            },
            {
                "slug": "salsa-linea",
                "confidence": 0.65,
                "evidence": "Salsa En Línea",
            },
        ],
    },
    {
        "name": "Más Danza",
        "description": (
            "Academia de danza en Maipú: salsa, bachata, ballet, K-pop y más."
        ),
        "candidate_url": "https://www.masdanza.cl/",
        "locations": [
            {
                "label": "Maipú",
                "address": "Avenida Sur 1626",
                "comuna": "Maipú",
                "source_url": "https://www.masdanza.cl/",
            }
        ],
        "links": [
            {"kind": "web", "url": "https://www.masdanza.cl/"},
            {"kind": "phone", "url": "tel:+56979866495"},
        ],
        "styles": [],
    },
    {
        "name": "Academia Solar",
        "description": (
            "Clases de baile en Santiago: salsa cubana, casino, bachata, "
            "afro-cubano y más."
        ),
        "candidate_url": "https://www.facebook.com/3mas2dancestudio/",
        "locations": [
            {
                "label": "Santiago",
                "comuna": "Santiago",
                "source_url": "https://www.facebook.com/3mas2dancestudio/",
            }
        ],
        "links": [
            {
                "kind": "facebook",
                "url": "https://www.facebook.com/3mas2dancestudio/",
            }
        ],
        "styles": [
            {
                "slug": "salsa-cubana",
                "confidence": 0.9,
                "evidence": "Salsa Cubana, Casino",
            }
        ],
    },
    {
        "name": "Escuela Moderna",
        "description": (
            "Taller de bailes latinos en Vitacura y Bellavista: salsa, salsa "
            "casino, bachata, merengue y más."
        ),
        "candidate_url": "https://emoderna.cl/talleres/bailes-latinos-2/",
        "locations": [
            {
                "label": "Vitacura",
                "address": "Luis Pasteur 5303",
                "comuna": "Vitacura",
                "source_url": "https://emoderna.cl/talleres/bailes-latinos-2/",
            },
            {
                "label": "Bellavista",
                "address": "Chucre Manzur",
                "comuna": "Providencia",
                "source_url": "https://emoderna.cl/talleres/bailes-latinos-2/",
            },
        ],
        "links": [
            {"kind": "web", "url": "https://emoderna.cl/"},
            {"kind": "instagram", "url": "https://instagram.com/escuelamoderna"},
            {"kind": "facebook", "url": "https://facebook.com/escuelamoderna"},
            {"kind": "tiktok", "url": "https://tiktok.com/@escuelamoderna"},
            {"kind": "phone", "url": "tel:+56954163911"},
        ],
        "styles": [
            {
                "slug": "salsa-cubana",
                "confidence": 0.9,
                "evidence": "Salsa-casino",
            }
        ],
    },
    {
        "name": "Bailando por Siempre",
        "description": (
            "Clases de baile latino en Las Condes, Vitacura, La Reina, "
            "Providencia y Lo Barnechea: salsa tradicional y en línea, mambo, "
            "bachata y más."
        ),
        "candidate_url": "https://bailando.cl/",
        "locations": [
            {
                "label": "Las Condes",
                "comuna": "Las Condes",
                "source_url": "https://bailando.cl/",
            },
            {
                "label": "Vitacura",
                "comuna": "Vitacura",
                "source_url": "https://bailando.cl/",
            },
            {
                "label": "La Reina",
                "comuna": "La Reina",
                "source_url": "https://bailando.cl/",
            },
            {
                "label": "Providencia",
                "comuna": "Providencia",
                "source_url": "https://bailando.cl/",
            },
            {
                "label": "Lo Barnechea",
                "comuna": "Lo Barnechea",
                "source_url": "https://bailando.cl/",
            },
        ],
        "links": [
            {"kind": "web", "url": "https://bailando.cl/"},
            {
                "kind": "instagram",
                "url": "https://instagram.com/bailando_por_siempre",
            },
            {
                "kind": "facebook",
                "url": "https://facebook.com/Bailando.Academia",
            },
        ],
        "styles": [
            {
                "slug": "salsa-linea",
                "confidence": 0.9,
                "evidence": "Salsa en Línea",
            },
            {"slug": "mambo", "confidence": 0.65, "evidence": "Mambo"},
        ],
    },
    {
        "name": "Estudio de Danza Francisca García",
        "description": (
            "Estudio de danza en Vitacura: salsa casino, salsa en línea, "
            "salsa On2, bachata y más."
        ),
        "candidate_url": "https://www.elestudiodedanza.cl/salsa",
        "locations": [
            {
                "label": "Vitacura",
                "address": "Av. Vitacura 8751",
                "comuna": "Vitacura",
                "source_url": "https://www.elestudiodedanza.cl/salsa",
            }
        ],
        "links": [
            {"kind": "web", "url": "https://www.elestudiodedanza.cl/"},
            {
                "kind": "instagram",
                "url": "https://instagram.com/elestudiodedanza",
            },
            {
                "kind": "email",
                "url": "mailto:elestudiodedanza@gmail.com",
            },
        ],
        "styles": [
            {
                "slug": "salsa-cubana",
                "confidence": 0.9,
                "evidence": "Salsa Casino",
            },
            {
                "slug": "salsa-linea",
                "confidence": 0.9,
                "evidence": "Salsa en línea / On2",
            },
        ],
    },
    {
        "name": "Muévete on Tour",
        "description": "Clases de salsa y bachata en San Miguel y Ñuñoa.",
        "candidate_url": "https://www.facebook.com/mueveteontour/",
        "locations": [
            {
                "label": "San Miguel",
                "comuna": "San Miguel",
                "source_url": "https://www.facebook.com/mueveteontour/",
            },
            {
                "label": "Ñuñoa",
                "comuna": "Ñuñoa",
                "source_url": "https://www.facebook.com/mueveteontour/",
            },
        ],
        "links": [
            {
                "kind": "facebook",
                "url": "https://www.facebook.com/mueveteontour/",
            }
        ],
        "styles": [],
    },
    {
        "name": "SBS Estudio",
        "description": "Clases de salsa y bachata.",
        "candidate_url": "https://www.instagram.com/sbsestudio_cl/?hl=es-la",
        "locations": [],
        "links": [
            {"kind": "instagram", "url": "https://instagram.com/sbsestudio_cl"}
        ],
        "styles": [],
    },
    {
        "name": "Bailemos Todos Chile",
        "description": None,
        "candidate_url": "https://www.instagram.com/bailemostodos_chile/?hl=es",
        "locations": [
            {
                "label": "Providencia",
                "comuna": "Providencia",
                "source_url": "https://www.instagram.com/bailemostodos_chile/?hl=es",
            }
        ],
        "links": [
            {
                "kind": "instagram",
                "url": "https://instagram.com/bailemostodos_chile",
            }
        ],
        "styles": [],
    },
]


EXCLUDED_NAMES = {
    "academia mc | danza, teatro, artes marciales y más en ...",
    "clases de salsa en puente alto",
    "cursos - sonarte",
}


def _reject_excluded(conn) -> None:
    rows = conn.execute(
        """
        select id, payload->>'name' as name
        from proposals
        where status = 'pending'
        """
    ).fetchall()
    for row in rows:
        name = (row["name"] or "").strip()
        if name.lower() in EXCLUDED_NAMES:
            reject(conn, row["id"])
            print(f"REJ {name}")


def _find_candidate_id(conn, url: str) -> str | None:
    row = conn.execute(
        "select id from candidates where url = %s", (url,)
    ).fetchone()
    if row:
        return row["id"]

    row = conn.execute(
        "select id from candidates where url like %s order by length(url) asc limit 1",
        (url.rstrip("/") + "%",),
    ).fetchone()
    if row:
        return row["id"]

    domain = domain_of(url)
    if domain and domain != "facebook.com":
        row = conn.execute(
            "select id from candidates where url like %s order by length(url) asc limit 1",
            (f"%{domain}%",),
        ).fetchone()
        if row:
            return row["id"]
    return None


def _publish_one(conn, item: dict) -> str:
    payload = validate_payload(
        {
            "name": item["name"],
            "description": item["description"],
            "locations": item["locations"],
            "links": item["links"],
            "styles": item["styles"],
        }
    )

    candidate_id = _find_candidate_id(conn, item["candidate_url"])
    if candidate_id is None:
        comuna = item["locations"][0].get("comuna") if item["locations"] else None
        candidate_id = upsert_candidate(
            conn,
            Candidate(
                name=item["name"],
                url=item["candidate_url"],
                handle=None,
                source="manual",
                comuna=comuna,
                raw={"validated": True},
            ),
        )

    slug = slugify(item["name"])
    existing = conn.execute(
        "select id from academies where slug = %s", (slug,)
    ).fetchone()
    academy_id = existing["id"] if existing else None
    kind = "update" if academy_id else "create"

    evidence = {
        "name": {
            "source_url": item["candidate_url"],
            "method": "manual_validation",
        }
    }
    proposal_id = insert_proposal(
        conn,
        candidate_id=candidate_id,
        academy_id=academy_id,
        kind=kind,
        payload=payload,
        evidence=evidence,
        confidence=1.0,
    )
    if proposal_id is None:
        dedupe_key = proposal_dedupe_key(
            kind, academy_id or candidate_id, payload
        )
        row = conn.execute(
            "select id from proposals where dedupe_key = %s", (dedupe_key,)
        ).fetchone()
        if row is None:
            raise RuntimeError(f"no se pudo crear ni encontrar propuesta: {slug}")
        proposal_id = row["id"]

    return approve(conn, proposal_id, payload=payload, verify=True)


def main() -> int:
    config = load()
    if not config.database_url:
        print("Falta DATABASE_URL", file=sys.stderr)
        return 2

    conn = connect(config.database_url)
    failures: list[tuple[str, str]] = []
    published: list[tuple[str, str]] = []
    try:
        for item in ACADEMIES:
            try:
                academy_id = _publish_one(conn, item)
                conn.commit()
                published.append((item["name"], academy_id))
                print(f"OK  {item['name']} -> {academy_id}")
            except Exception as exc:  # noqa: BLE001 - reportar y seguir
                conn.rollback()
                failures.append((item["name"], str(exc)))
                print(f"ERR {item['name']}: {exc}", file=sys.stderr)

        try:
            _reject_excluded(conn)
            conn.commit()
        except Exception as exc:  # noqa: BLE001 - reportar y seguir
            conn.rollback()
            failures.append(("rechazos", str(exc)))
            print(f"ERR rechazos: {exc}", file=sys.stderr)
    finally:
        conn.close()

    print(f"\npublicadas={len(published)} fallidas={len(failures)}")
    if failures:
        for name, error in failures:
            print(f"  - {name}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
