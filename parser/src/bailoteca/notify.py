"""Correo de aviso cuando la corrida guarda propuestas nuevas."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:
    from bailoteca.config import Config
    from bailoteca.propose import ProposalDraft
    from bailoteca.run import RunSummary


@dataclass(frozen=True)
class Email:
    subject: str
    html: str
    text: str


@dataclass(frozen=True)
class Email:
    subject: str
    html: str
    text: str


def _escape(value: object) -> str:
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def actions_url_from_env(env: Mapping[str, str]) -> str | None:
    repo = env.get("GITHUB_REPOSITORY")
    run_id = env.get("GITHUB_RUN_ID")
    if not repo or not run_id:
        return None
    return f"https://github.com/{repo}/actions/runs/{run_id}"


def _proposal_name(draft: "ProposalDraft") -> str:
    name = (draft.payload or {}).get("name")
    if name is None or str(name).strip() == "":
        return "(sin nombre)"
    return str(name)


def build_review_email(
    drafts: "list[ProposalDraft]",
    summary: "RunSummary",
    *,
    day: str,
    actions_url: str | None = None,
) -> Email:
    count = len(drafts)
    plural = "propuestas" if count != 1 else "propuesta"
    subject = f"Bailoteca: {count} {plural} nueva{'s' if count != 1 else ''} para revisar"

    # Texto plano
    text_lines = [
        "Bailoteca — propuestas nuevas para revisar",
        "",
        f"corrida: {day}",
        f"propuestas: {summary.proposals} (dudosas: {summary.needs_review})",
        f"duplicados: {summary.duplicates}",
        f"enlaces muertos: {summary.dead_links}",
        f"duración: {summary.duration_s} s",
        "",
        "Propuestas:",
    ]
    for draft in drafts:
        name = _proposal_name(draft)
        text_lines.append(
            f"- {name} — {draft.kind} — confianza {draft.confidence:.2f} — "
            f"dudosa: {'sí' if draft.needs_review else 'no'}"
        )
    if actions_url:
        text_lines.extend(["", f"Actions: {actions_url}"])
    text_lines.extend(
        [
            "",
            f"Reporte: reports/{day}/review.md",
            "Revisa con: cd parser && python -m bailoteca review",
        ]
    )
    text = "\n".join(text_lines)

    # HTML
    rows = []
    for draft in drafts:
        name = _escape(_proposal_name(draft))
        rows.append(
            "<tr>"
            f"<td style=\"padding:6px 0;color:#3e3a4a;font-weight:bold;\">{name}</td>"
            f"<td style=\"padding:6px 0;color:#6c6880;\">{_escape(draft.kind)}</td>"
            f"<td style=\"padding:6px 0;color:#6c6880;\">{draft.confidence:.2f}</td>"
            f"<td style=\"padding:6px 0;color:#6c6880;\">"
            f"{'sí' if draft.needs_review else 'no'}</td>"
            "</tr>"
        )
    rows_html = "".join(rows)
    actions_html = (
        f'<p style="margin:16px 0 0;"><a href="{_escape(actions_url)}">'
        f"{_escape(actions_url)}</a></p>"
        if actions_url
        else ""
    )
    html = (
        "<!doctype html><html lang=\"es\"><body style=\"margin:0;background:#fdfbf7;"
        "font-family:Arial,Helvetica,sans-serif;color:#3e3a4a;\">"
        '<div style="max-width:560px;margin:0 auto;padding:24px;">'
        '<div style="background:#ffffff;border:1px solid #ece7f3;border-radius:16px;'
        'overflow:hidden;">'
        '<div style="background:#efeaf8;padding:20px 24px;">'
        '<p style="margin:0;font-size:12px;letter-spacing:2px;text-transform:uppercase;'
        'color:#6c6880;">Bailoteca</p>'
        f'<h1 style="margin:6px 0 0;font-size:20px;font-weight:bold;">'
        f"{count} {plural} nueva{'s' if count != 1 else ''} para revisar</h1>"
        "</div>"
        '<div style="padding:24px;">'
        f"<p style=\"margin:0 0 12px;\">Corrida del {_escape(day)}</p>"
        "<table style=\"width:100%;border-collapse:collapse;font-size:14px;\">"
        "<thead><tr>"
        '<th style="text-align:left;padding:6px 0;color:#6c6880;">Nombre</th>'
        '<th style="text-align:left;padding:6px 0;color:#6c6880;">Tipo</th>'
        '<th style="text-align:left;padding:6px 0;color:#6c6880;">Confianza</th>'
        '<th style="text-align:left;padding:6px 0;color:#6c6880;">Dudosa</th>'
        "</tr></thead>"
        f"<tbody>{rows_html}</tbody></table>"
        f"{actions_html}"
        f'<p style="margin:16px 0 0;font-size:13px;color:#6c6880;">'
        f"Reporte: reports/{_escape(day)}/review.md<br>"
        "Revisa con: cd parser &amp;&amp; python -m bailoteca review</p>"
        "</div></div></div></body></html>"
    )

    return Email(subject=subject, html=html, text=text)


def send_review_email(
    drafts: "list[ProposalDraft]",
    summary: "RunSummary",
    config: "Config",
    *,
    http=None,
    actions_url: str | None = None,
    day: str | None = None,
) -> bool:
    if not config.resend_api_key:
        logging.warning("Correo de revisión omitido: falta RESEND_API_KEY.")
        return False
    if not config.review_to_email:
        logging.warning("Correo de revisión omitido: falta BAILOTECA_REVIEW_TO_EMAIL.")
        return False

    if day is None:
        day = datetime.now(timezone.utc).date().isoformat()

    email = build_review_email(drafts, summary, day=day, actions_url=actions_url)

    close_http = False
    if http is None:
        import httpx

        http = httpx.Client(timeout=10)
        close_http = True

    try:
        response = http.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {config.resend_api_key}"},
            json={
                "from": config.review_from_email,
                "to": config.review_to_email,
                "subject": email.subject,
                "html": email.html,
                "text": email.text,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logging.warning("No se pudo enviar el correo de revisión: %s", exc)
        if close_http:
            http.close()
        return False

    if close_http:
        http.close()

    if getattr(response, "status_code", 0) >= 400:
        try:
            message = response.json().get("message", "")
        except Exception:  # noqa: BLE001
            message = ""
        logging.warning(
            "Resend rechazó el correo de revisión (HTTP %s): %s",
            response.status_code,
            message,
        )
        return False
    return True
