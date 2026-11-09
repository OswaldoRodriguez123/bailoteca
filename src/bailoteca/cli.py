"""Command line interface for the dance directory pipeline."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path


def _load_config():
    from bailoteca.config import load

    return load()


def _open_conn(config):
    from bailoteca.db import connect

    if not config.database_url:
        print(
            "Falta DATABASE_URL. Configúrala en .env o en el entorno.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return connect(config.database_url)


def _print_summary(summary) -> None:
    print(
        f"descubiertos={summary.discovered} "
        f"nuevos={summary.new_candidates} "
        f"propuestas={summary.proposals} "
        f"dudosas={summary.needs_review} "
        f"enlaces_muertos={summary.dead_links}"
    )


def cmd_run(args: argparse.Namespace) -> int:
    from bailoteca.run import run

    summary = run(_load_config(), dry_run=args.dry_run)
    _print_summary(summary)
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    from bailoteca.db import pending_proposals
    from bailoteca.review import render_review

    conn = _open_conn(_load_config())
    try:
        print(render_review(pending_proposals(conn)))
    finally:
        conn.rollback()
        conn.close()
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    from bailoteca.publish import approve

    conn = _open_conn(_load_config())
    try:
        academy_id = approve(
            conn, args.proposal_id, verify=not args.unverified
        )
        conn.commit()
        print(academy_id)
    finally:
        conn.close()
    return 0


def cmd_edit(args: argparse.Namespace) -> int:
    from bailoteca.publish import approve

    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if not editor:
        print("Define EDITOR o VISUAL para editar la propuesta.", file=sys.stderr)
        return 2

    conn = _open_conn(_load_config())
    path = None
    try:
        row = conn.execute(
            "select payload from proposals where id = %s", (args.proposal_id,)
        ).fetchone()
        if row is None:
            print(f"propuesta no encontrada: {args.proposal_id}", file=sys.stderr)
            return 2
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as handle:
            json.dump(row["payload"], handle, ensure_ascii=False, indent=2)
            path = handle.name
        subprocess.run([editor, path], check=False)
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        academy_id = approve(conn, args.proposal_id, payload=payload)
        conn.commit()
        print(academy_id)
    finally:
        if path:
            Path(path).unlink(missing_ok=True)
        conn.close()
    return 0


def cmd_reject(args: argparse.Namespace) -> int:
    from bailoteca.publish import reject

    conn = _open_conn(_load_config())
    try:
        reject(conn, args.proposal_id)
        conn.commit()
    finally:
        conn.close()
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    from bailoteca.classify import classify
    from bailoteca.db import insert_proposal, upsert_candidate
    from bailoteca.enrich import CachedFetcher, HttpxFetcher, enrich
    from bailoteca.propose import build_proposal
    from bailoteca.run import parse_add_target

    config = _load_config()
    candidate = parse_add_target(args.target)
    enriched = enrich(
        candidate, CachedFetcher(HttpxFetcher(), config.cache_dir)
    )
    text = " ".join(
        part for part in (enriched.description, enriched.text) if part
    )
    hits = classify(text, None)
    draft = build_proposal(candidate, enriched, hits, None, set())

    conn = _open_conn(config)
    try:
        candidate_id = upsert_candidate(conn, candidate)
        if draft is None:
            print("sin propuesta: la academia ya existe")
            conn.commit()
            return 0
        proposal_id = insert_proposal(
            conn,
            candidate_id=candidate_id,
            academy_id=None,
            kind="create",
            payload=draft.payload,
            evidence=draft.evidence,
            confidence=draft.confidence,
        )
        conn.commit()
        print(proposal_id or "propuesta duplicada")
    finally:
        conn.close()
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    from bailoteca.run import refresh

    summary = refresh(_load_config(), args.slug)
    _print_summary(summary)
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    from bailoteca.db import list_published

    conn = _open_conn(_load_config())
    try:
        academies = list_published(conn)
    finally:
        conn.rollback()
        conn.close()

    if not args.csv:
        print(json.dumps(academies, ensure_ascii=False, indent=2, default=str))
        return 0

    writer = csv.writer(sys.stdout)
    writer.writerow(
        [
            "slug",
            "name",
            "description",
            "comuna",
            "address",
            "styles",
            "instagram",
            "web",
            "verified_at",
        ]
    )
    for academy in academies:
        locations = academy["locations"]
        links = academy["links"]
        writer.writerow(
            [
                academy["slug"],
                academy["name"],
                academy["description"] or "",
                locations[0]["comuna"] if locations else "",
                locations[0]["address"] if locations else "",
                "|".join(style["slug"] for style in academy["styles"]),
                next(
                    (
                        link["url"]
                        for link in links
                        if link["kind"] == "instagram"
                    ),
                    "",
                ),
                next(
                    (link["url"] for link in links if link["kind"] == "web"),
                    "",
                ),
                academy["verified_at"] or "",
            ]
        )
    return 0


def cmd_spike(args: argparse.Namespace) -> int:
    import subprocess
    import sys

    script = Path(__file__).parent.parent / "scripts" / "osm_spike.py"
    if not script.exists():
        script = Path(__file__).parent / "osm_spike.py"
    cmd = [sys.executable, str(script)]
    if args.fixture:
        cmd.extend(["--fixture", args.fixture])
    result = subprocess.run(cmd)
    return result.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bailoteca",
        description="Bailoteca: directorio de academias de baile — descubrir, revisar y publicar.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Descubrir candidatos y generar propuestas")
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="Escribir reportes sin tocar la base de datos",
    )
    run.set_defaults(handler=cmd_run)

    review = subparsers.add_parser("review", help="Mostrar las propuestas pendientes")
    review.set_defaults(handler=cmd_review)

    approve = subparsers.add_parser("approve", help="Aprobar y publicar una propuesta")
    approve.add_argument("proposal_id")
    approve.add_argument(
        "--unverified",
        action="store_true",
        help="Publicar sin fijar verified_at (fichas incompletas)",
    )
    approve.set_defaults(handler=cmd_approve)

    edit = subparsers.add_parser("edit", help="Editar y aprobar una propuesta")
    edit.add_argument("proposal_id")
    edit.set_defaults(handler=cmd_edit)

    reject = subparsers.add_parser("reject", help="Rechazar una propuesta")
    reject.add_argument("proposal_id")
    reject.set_defaults(handler=cmd_reject)

    add = subparsers.add_parser("add", help="Agregar una academia a mano")
    add.add_argument("target", help="Handle de Instagram, URL o nombre")
    add.set_defaults(handler=cmd_add)

    refresh = subparsers.add_parser("refresh", help="Releer una academia publicada")
    refresh.add_argument("slug")
    refresh.set_defaults(handler=cmd_refresh)

    export = subparsers.add_parser("export", help="Exportar las academias publicadas")
    export.add_argument("--csv", action="store_true", help="Escribir CSV a stdout")
    export.set_defaults(handler=cmd_export)

    spike = subparsers.add_parser("spike", help="Resumir la cobertura de OpenStreetMap")
    spike.add_argument("--fixture", help="Archivo JSON de Overpass ya descargado")
    spike.set_defaults(handler=cmd_spike)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler: Callable[[argparse.Namespace], int] = getattr(args, "handler", cmd_run)
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
