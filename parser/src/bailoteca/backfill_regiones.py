"""Backfill de ``academy_locations.region`` a partir de la comuna.

Deriva la región con el catálogo oficial compartido
(``bailoteca_shared.regions``). Sin ``--apply`` solo imprime el plan; con
``--apply`` escribe la región de las sedes que lograron match, por lo que
puede correrse varias veces sin efectos distintos (idempotente).
"""

from __future__ import annotations

from bailoteca_shared.regions import region_slug_for_comuna


def plan_backfill(rows: list[dict]) -> list[tuple[str, str | None]]:
    """rows: id, comuna → (id, region|None) usando bailoteca_shared.regions."""
    return [
        (row["id"], region_slug_for_comuna(row.get("comuna"))) for row in rows
    ]


def _rows_to_dicts(raw_rows) -> list[dict]:
    # La conexión real usa dict_row; el fake de los tests entrega tuplas.
    return [
        {"id": row["id"], "comuna": row["comuna"]}
        if isinstance(row, dict)
        else {"id": row[0], "comuna": row[1]}
        for row in raw_rows
    ]


def _print_table(rows: list[dict], plan: list[tuple[str, str | None]]) -> None:
    print(f"{'id':<36}  {'comuna':<28}  region")
    for row, (location_id, region) in zip(rows, plan):
        comuna = row.get("comuna") or "-"
        print(f"{location_id!s:<36}  {comuna:<28}  {region or '-'}")


def _print_summary(rows: list[dict], plan: list[tuple[str, str | None]]) -> None:
    matched = sum(1 for _, region in plan if region is not None)
    missing = sorted(
        {
            row.get("comuna") or "(sin comuna)"
            for row, (_, region) in zip(rows, plan)
            if region is None
        }
    )
    print(
        f"total={len(rows)} con_region={matched} "
        f"sin_match={len(rows) - matched}"
    )
    if missing:
        print("sin match: " + ", ".join(missing))


def run(conn, apply: bool = False) -> int:
    """Lee academy_locations(id, comuna). Sin --apply: imprime tabla y resumen,
    no escribe. Con --apply: update academy_locations set region=%s where id=%s
    (idempotente). Imprime siempre: total, con región, sin match (lista sus
    comunas). Devuelve 0."""
    raw_rows = conn.execute(
        "select id, comuna from academy_locations order by comuna, id"
    ).fetchall()
    rows = _rows_to_dicts(raw_rows)
    plan = plan_backfill(rows)

    if not apply:
        _print_table(rows, plan)

    updated = 0
    if apply:
        for location_id, region in plan:
            # Sin match no se toca la fila: evita borrar una región ya cargada.
            if region is None:
                continue
            conn.execute(
                "update academy_locations set region = %s where id = %s",
                (region, location_id),
            )
            updated += 1
        conn.commit()

    _print_summary(rows, plan)
    if apply:
        print(f"actualizadas={updated}")
    return 0
