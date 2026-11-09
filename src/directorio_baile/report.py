"""Reporte semanal en Markdown."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from directorio_baile.run import RunSummary


def render_weekly_report(
    summary: "RunSummary",
    dead_links: list[dict],
    stale: list[dict],
) -> str:
    lines = ["# Reporte semanal del directorio", ""]
    lines.append(f"- Candidatos descubiertos: {summary.discovered}")
    lines.append(f"- Candidatos nuevos: {summary.new_candidates}")
    lines.append(f"- Propuestas generadas: {summary.proposals}")
    lines.append(f"- Propuestas dudosas: {summary.needs_review}")
    lines.append(f"- Enlaces muertos: {summary.dead_links}")
    lines.append(f"- Duración: {summary.duration_s} s")

    lines.extend(["", "## Enlaces muertos", ""])
    if dead_links:
        lines.append("| Academia | Tipo | Enlace |")
        lines.append("| --- | --- | --- |")
        for item in dead_links:
            lines.append(
                f"| {item.get('name', item.get('slug', ''))} | "
                f"{item.get('kind', '')} | {item.get('url', '')} |"
            )
    else:
        lines.append("Sin enlaces muertos.")

    lines.extend(["", "## Academias por verificar", ""])
    if stale:
        lines.append("| Academia | Última verificación |")
        lines.append("| --- | --- |")
        for item in stale:
            lines.append(
                f"| {item.get('name', item.get('slug', ''))} | "
                f"{item.get('verified_at') or 'nunca'} |"
            )
    else:
        lines.append("Todas las academias están verificadas.")

    return "\n".join(lines)
