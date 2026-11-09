"""Reporte semanal en Markdown."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bailoteca.run import RunSummary


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


def stale_academies(
    academies: list[dict],
    days: int = 90,
    now: datetime | None = None,
) -> list[dict]:
    reference = now or datetime.now(timezone.utc)
    limit = reference - timedelta(days=days)
    stale: list[dict] = []
    for academy in academies:
        verified = academy.get("verified_at")
        if verified is None:
            stale.append(academy)
            continue
        if isinstance(verified, str):
            try:
                verified = datetime.fromisoformat(verified.replace("Z", "+00:00"))
            except ValueError:
                stale.append(academy)
                continue
        if verified.tzinfo is None:
            verified = verified.replace(tzinfo=timezone.utc)
        if verified < limit:
            stale.append(academy)
    return stale
