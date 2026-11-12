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
        f"filtrados_reglas={summary.filtered_rules} "
        f"duplicados={summary.duplicates} "
        f"filtrados_clef={summary.filtered_clef} "
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


def cmd_enrich_places(args: argparse.Namespace) -> int:
    from bailoteca.covers import BUCKET, download_image
    from bailoteca.db import list_published
    from bailoteca.places import fetch_place, to_dict

    config = _load_config()
    if not config.serpapi_key:
        print(
            "Falta SERPAPI_KEY. Configúrala en .env o en el entorno.",
            file=sys.stderr,
        )
        return 2

    import httpx
    from psycopg.types.json import Jsonb

    conn = _open_conn(config)
    http = httpx.Client(timeout=10)
    enriched = 0
    failed = 0
    storage = None
    storage_ready = False
    try:
        academies = list_published(conn)
        target_slug = getattr(args, "slug", None)
        force = getattr(args, "force", False)
        for academy in academies:
            if target_slug and academy.get("slug") != target_slug:
                continue
            if academy.get("google") and not force:
                # Ya tiene datos de Google Maps: no gastar cuota SerpApi.
                continue
            locations = academy.get("locations") or []
            loc = locations[0] if locations else {}
            info = fetch_place(
                academy["name"],
                loc.get("comuna"),
                loc.get("address"),
                loc.get("lat"),
                loc.get("lng"),
                http,
                config.serpapi_key,
            )
            if info is None:
                failed += 1
                continue
            data = to_dict(info)
            cover_url = None
            if info.thumbnail and not getattr(args, "dry_run", False):
                image = download_image(info.thumbnail, client=http, timeout=20.0)
                if image is None:
                    print(
                        f"aviso: no se pudo descargar la portada de Google Maps para {academy.get('slug')}",
                        file=sys.stderr,
                    )
                else:
                    if storage is None:
                        if not config.supabase_url or not config.supabase_service_role_key:
                            raise RuntimeError(
                                "Faltan SUPABASE_URL y/o SUPABASE_SERVICE_ROLE_KEY para alojar la portada de Google Maps."
                            )
                        from bailoteca.supabase_storage import StorageClient

                        storage = StorageClient(
                            config.supabase_url, config.supabase_service_role_key
                        )
                    if not storage_ready:
                        storage.ensure_bucket(BUCKET)
                        storage_ready = True
                    key = f"{academy['slug']}.jpg"
                    storage.upload(BUCKET, key, image, "image/jpeg")
                    cover_url = storage.public_url(BUCKET, key)
            if not getattr(args, "dry_run", False):
                sql = """
                    update academies set
                      google = %s,
                      updated_at = now()
                """
                params = [Jsonb(data["google"])]
                if cover_url:
                    sql += ",\n                      cover_url = %s,\n                      cover_source = %s,\n                      cover_fetched_at = now()"
                    params.extend([cover_url, "google"])
                sql += "\n                    where id = %s"
                params.append(academy["id"])
                conn.execute(sql, tuple(params))
            enriched += 1
        if not getattr(args, "dry_run", False):
            conn.commit()
    finally:
        http.close()
        conn.close()
    print(
        f"enriquecidas={enriched} fallidas={failed} total={len(academies)}"
    )
    return 0


def cmd_clear_places(args: argparse.Namespace) -> int:
    """Borra los datos de Google Maps de una o varias academias (sin SerpApi)."""
    config = _load_config()
    conn = _open_conn(config)
    cleared = 0
    try:
        for slug in args.slugs:
            cur = conn.execute(
                "update academies set google = null, updated_at = now() where slug = %s",
                (slug,),
            )
            if cur.rowcount:
                cleared += cur.rowcount
                print(f"borrado: {slug}")
            else:
                print(f"no encontrada: {slug}")
        conn.commit()
    finally:
        conn.close()
    print(f"borradas={cleared}")
    return 0


def cmd_refresh_images(args: argparse.Namespace) -> int:
    from bailoteca.images import refresh_images

    summary = refresh_images(_load_config(), dry_run=getattr(args, "dry_run", False))
    print(
        f"revisadas={summary['checked']} "
        f"actualizadas={summary['updated']} "
        f"mantienen_google={summary['kept_google']} "
        f"al_dia={summary['fresh']} "
        f"sin_imagen={summary['no_image']}"
    )
    return 0


def cmd_backfill_regiones(args: argparse.Namespace) -> int:
    from bailoteca.backfill_regiones import run

    conn = _open_conn(_load_config())
    try:
        return run(conn, apply=args.apply)
    finally:
        conn.close()


def cmd_host_covers(args: argparse.Namespace) -> int:
    from bailoteca.covers import backfill_covers

    recovered_sources: dict[str, str] = {}
    manifest = getattr(args, "recovered_manifest", None)
    if manifest:
        path = Path(manifest)
        if not path.exists():
            print(f"No existe el manifiesto: {path}", file=sys.stderr)
            return 2
        recovered_sources = json.loads(path.read_text(encoding="utf-8"))

    config = _load_config()
    if not config.database_url:
        print(
            "Falta DATABASE_URL. Configúrala en .env o en el entorno.",
            file=sys.stderr,
        )
        return 2
    try:
        summary = backfill_covers(
            config,
            recovered_sources,
            dry_run=getattr(args, "dry_run", False),
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(
        f"subidas={len(summary['hosted'])} "
        f"omitidas={len(summary['skipped'])} "
        f"sin_imagen={len(summary['missing'])} "
        f"fallidas={len(summary['failed'])}"
    )
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

    enrich_places = subparsers.add_parser(
        "enrich-places", help="Enriquecer academias con datos de Google Maps"
    )
    enrich_places.add_argument(
        "--dry-run",
        action="store_true",
        help="No escribir en la base de datos",
    )
    enrich_places.add_argument(
        "--slug",
        help="Enriquecer solo la academia con este slug",
    )
    enrich_places.add_argument(
        "--force",
        action="store_true",
        help="Re-enriquecer aunque ya tenga datos de Google Maps",
    )
    enrich_places.set_defaults(handler=cmd_enrich_places)

    clear_places = subparsers.add_parser(
        "clear-places",
        help="Borrar los datos de Google Maps de academias (sin SerpApi)",
    )
    clear_places.add_argument("slugs", nargs="+", help="Slugs de las academias")
    clear_places.set_defaults(handler=cmd_clear_places)

    refresh_images = subparsers.add_parser(
        "refresh-images",
        help="Re-firmar portadas desde og:image (Instagram/Facebook/web)",
    )
    refresh_images.add_argument(
        "--dry-run",
        action="store_true",
        help="Imprime los cambios sin escribir en la base de datos",
    )
    refresh_images.set_defaults(handler=cmd_refresh_images)

    backfill_regiones = subparsers.add_parser(
        "backfill-regiones",
        help="Completar academy_locations.region desde la comuna",
    )
    backfill_regiones.add_argument(
        "--apply",
        action="store_true",
        help="Escribe las regiones en la base de datos (por defecto solo muestra el plan)",
    )
    backfill_regiones.set_defaults(handler=cmd_backfill_regiones)

    host_covers = subparsers.add_parser(
        "host-covers",
        help="Alojar las portadas actuales en Supabase Storage (backfill)",
    )
    host_covers.add_argument(
        "--recovered-manifest",
        help="JSON opcional {slug: url de la portada original} para academias rotas",
    )
    host_covers.add_argument(
        "--dry-run",
        action="store_true",
        help="Descarga y valida sin subir ni escribir en la base de datos",
    )
    host_covers.set_defaults(handler=cmd_host_covers)

    export = subparsers.add_parser("export", help="Exportar las academias publicadas")
    export.add_argument("--csv", action="store_true", help="Escribir CSV a stdout")
    export.set_defaults(handler=cmd_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler: Callable[[argparse.Namespace], int] = getattr(args, "handler", cmd_run)
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
