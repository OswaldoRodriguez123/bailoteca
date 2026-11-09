"""Renderizado en Markdown de las propuestas pendientes."""

from __future__ import annotations

from bailoteca.classify import AUTO_CONFIDENCE


def _is_doubtful(proposal: dict) -> bool:
    payload = proposal.get("payload") or {}
    confidence = proposal.get("confidence")
    if confidence is not None and confidence < AUTO_CONFIDENCE:
        return True
    return any(style.get("disputed") for style in payload.get("styles") or [])


def render_review(proposals: list[dict]) -> str:
    lines = ["# Propuestas pendientes", ""]
    if not proposals:
        lines.append("No hay propuestas pendientes.")
        return "\n".join(lines)

    for proposal in proposals:
        payload = proposal.get("payload") or {}
        title = payload.get("name") or "(sin nombre)"
        marker = "  [DUDOSO]" if _is_doubtful(proposal) else ""
        lines.append(f"## {title}{marker}")
        lines.append(f"- tipo: {proposal.get('kind', 'create')}")

        if proposal.get("confidence") is not None:
            lines.append(f"- confianza: {proposal['confidence']}")

        locations = payload.get("locations") or []
        if locations:
            first = locations[0]
            if first.get("comuna"):
                lines.append(f"- comuna: {first['comuna']}")
            if first.get("address"):
                lines.append(f"- dirección: {first['address']}")

        styles = payload.get("styles") or []
        if styles:
            rendered = ", ".join(
                f"{style.get('slug')} ({style.get('confidence')})"
                for style in styles
            )
            lines.append(f"- estilos: {rendered}")

        links = payload.get("links") or []
        if links:
            lines.append("- enlaces:")
            for link in links:
                lines.append(f"  - {link.get('kind')}: {link.get('url')}")

        evidence = proposal.get("evidence") or {}
        if evidence:
            lines.append("- evidencia:")
            for field, info in evidence.items():
                if isinstance(info, dict):
                    source = info.get("source_url") or "sin fuente"
                    confidence = info.get("confidence", "n/d")
                    lines.append(f"  - {field}: {source} (confianza {confidence})")
                else:
                    lines.append(f"  - {field}: {info}")

        lines.append(f"- id: {proposal.get('id')}")
        lines.append("")

    return "\n".join(lines)
