from bailoteca.notify import actions_url_from_env, build_review_email
from bailoteca.propose import ProposalDraft
from bailoteca.run import RunSummary


def _draft(name, kind="create", confidence=0.8, needs_review=False):
    return ProposalDraft(
        kind=kind,
        candidate_id=None,
        academy_id=None,
        payload={"name": name},
        evidence={},
        confidence=confidence,
        dedupe_key=name,
        needs_review=needs_review,
    )


def test_subject_and_counts():
    drafts = [
        _draft("Salsa Norte"),
        _draft("Bachata Sur", kind="update", needs_review=True),
    ]
    summary = RunSummary(proposals=2, needs_review=1, duplicates=3, dead_links=1)
    email = build_review_email(drafts, summary, day="2026-11-11")
    assert email.subject == "Bailoteca: 2 propuestas nuevas para revisar"
    assert "Salsa Norte" in email.text
    assert "Bachata Sur" in email.text
    assert "update" in email.text
    assert "duplicados: 3" in email.text
    assert "python -m bailoteca review" in email.text


def test_single_proposal_subject_is_singular():
    email = build_review_email([_draft("Salsa Norte")], RunSummary(proposals=1), day="2026-11-11")
    assert email.subject == "Bailoteca: 1 propuesta nueva para revisar"


def test_build_review_email_escapes_html():
    email = build_review_email(
        [_draft("<b>Salsa & Cía</b>")], RunSummary(proposals=1), day="2026-11-11"
    )
    assert "<b>Salsa" not in email.html
    assert "&lt;b&gt;Salsa &amp; Cía&lt;/b&gt;" in email.html


def test_build_review_email_includes_actions_url():
    email = build_review_email(
        [_draft("Salsa Norte")],
        RunSummary(proposals=1),
        day="2026-11-11",
        actions_url="https://github.com/o/r/actions/runs/1",
    )
    assert "https://github.com/o/r/actions/runs/1" in email.text
    assert "https://github.com/o/r/actions/runs/1" in email.html


def test_actions_url_from_env():
    assert (
        actions_url_from_env({"GITHUB_REPOSITORY": "o/r", "GITHUB_RUN_ID": "42"})
        == "https://github.com/o/r/actions/runs/42"
    )
    assert actions_url_from_env({}) is None
