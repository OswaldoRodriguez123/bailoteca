import logging

from bailoteca.config import Config
from bailoteca.notify import actions_url_from_env, build_review_email, send_review_email
from bailoteca.propose import ProposalDraft
from bailoteca.run import RunSummary


class _FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code

    def json(self):
        return {"id": "email_1"} if self.status_code < 400 else {"message": "boom"}


class _FakeHttp:
    def __init__(self, status_code=200):
        self.status_code = status_code
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _FakeResponse(self.status_code)


def _config(**overrides):
    env = {
        "RESEND_API_KEY": "re_key",
        "BAILOTECA_REVIEW_TO_EMAIL": "yo@example.com",
    }
    env.update(overrides)
    return Config.from_env(env)


def test_send_without_credentials_is_noop():
    http = _FakeHttp()
    sent = send_review_email(
        [_draft("Salsa Norte")],
        RunSummary(proposals=1),
        Config.from_env({}),
        http=http,
    )
    assert sent is False
    assert http.calls == []


def test_send_posts_to_resend():
    http = _FakeHttp()
    sent = send_review_email(
        [_draft("Salsa Norte")],
        RunSummary(proposals=1),
        _config(),
        http=http,
        day="2026-11-11",
    )
    assert sent is True
    url, kwargs = http.calls[0]
    assert url == "https://api.resend.com/emails"
    assert kwargs["headers"]["Authorization"] == "Bearer re_key"
    assert kwargs["json"]["from"] == "onboarding@resend.dev"
    assert kwargs["json"]["to"] == "yo@example.com"
    assert "Salsa Norte" in kwargs["json"]["html"]


def test_send_error_returns_false_without_raising(caplog):
    http = _FakeHttp(status_code=422)
    with caplog.at_level(logging.WARNING):
        sent = send_review_email(
            [_draft("Salsa Norte")], RunSummary(proposals=1), _config(), http=http
        )
    assert sent is False
    assert "correo" in caplog.text


def test_send_network_error_returns_false():
    class _Boom:
        def post(self, url, **kwargs):
            raise OSError("sin red")

    assert (
        send_review_email(
            [_draft("Salsa Norte")], RunSummary(proposals=1), _config(), http=_Boom()
        )
        is False
    )


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
