"""Command line interface for the dance directory pipeline."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable


def _not_implemented(args: argparse.Namespace) -> int:
    print("not implemented", file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dance",
        description="Directorio de academias de baile: descubrir, revisar y publicar.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Descubrir candidatos y generar propuestas")
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="Escribir reportes sin tocar la base de datos",
    )
    run.set_defaults(handler=_not_implemented)

    review = subparsers.add_parser("review", help="Mostrar las propuestas pendientes")
    review.set_defaults(handler=_not_implemented)

    approve = subparsers.add_parser("approve", help="Aprobar y publicar una propuesta")
    approve.add_argument("proposal_id")
    approve.set_defaults(handler=_not_implemented)

    edit = subparsers.add_parser("edit", help="Editar y aprobar una propuesta")
    edit.add_argument("proposal_id")
    edit.set_defaults(handler=_not_implemented)

    reject = subparsers.add_parser("reject", help="Rechazar una propuesta")
    reject.add_argument("proposal_id")
    reject.set_defaults(handler=_not_implemented)

    add = subparsers.add_parser("add", help="Agregar una academia a mano")
    add.add_argument("target", help="Handle de Instagram, URL o nombre")
    add.set_defaults(handler=_not_implemented)

    refresh = subparsers.add_parser("refresh", help="Releer una academia publicada")
    refresh.add_argument("slug")
    refresh.set_defaults(handler=_not_implemented)

    export = subparsers.add_parser("export", help="Exportar las academias publicadas")
    export.add_argument("--csv", action="store_true", help="Escribir CSV a stdout")
    export.set_defaults(handler=_not_implemented)

    spike = subparsers.add_parser("spike", help="Resumir la cobertura de OpenStreetMap")
    spike.set_defaults(handler=_not_implemented)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler: Callable[[argparse.Namespace], int] = getattr(
        args, "handler", _not_implemented
    )
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
