import subprocess
import sys


def test_module_help_lists_commands():
    result = subprocess.run(
        [sys.executable, "-m", "bailoteca", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    for command in ("run", "review", "approve", "add", "refresh", "enrich-places", "host-covers"):
        assert command in result.stdout


def test_review_skip_osm_renders_country_line(monkeypatch, capsys):
    import argparse

    from bailoteca import cli

    class FakeConn:
        def rollback(self):
            pass
        def close(self):
            pass

    proposal = {
        "id": "p1",
        "confidence": 0.9,
        "kind": "create",
        "payload": {
            "name": "Academia X",
            "styles": [],
            "locations": [{"address": "Av. Siempre Viva 123", "comuna": "Providencia"}],
            "links": [{"kind": "web", "url": "https://x.cl/"}],
        },
        "evidence": {},
    }

    monkeypatch.setattr(cli, "_load_config", lambda: object())
    monkeypatch.setattr(cli, "_open_conn", lambda config: FakeConn())

    import bailoteca.db as db

    monkeypatch.setattr(db, "pending_proposals", lambda conn: [proposal])

    rc = cli.cmd_review(argparse.Namespace(skip_osm=True))
    out = capsys.readouterr().out
    assert rc == 0
    assert "- país: 🇨🇱 Chile probable" in out


def test_snapshot_from_payload_extracts_locations_links_and_comuna():
    from bailoteca.cli import _snapshot_from_payload

    snap = _snapshot_from_payload(
        {
            "name": "Academia X",
            "locations": [{"address": "Sarmiento 1729, San Miguel", "comuna": "San Miguel"}],
            "links": [
                {"kind": "web", "url": "https://x.cl/"},
                {"kind": "phone", "url": "tel:+56912345678"},
                {"kind": "email", "url": "mailto:a@b.cl"},
            ],
            "source_urls": ["https://fb.com/academiax"],
        }
    )
    assert snap.name == "Academia X"
    assert "https://x.cl/" in snap.urls
    assert "https://fb.com/academiax" in snap.urls
    assert snap.phones == ("tel:+56912345678",)
    assert snap.address_texts == ("Sarmiento 1729, San Miguel",)
    assert snap.comuna == "San Miguel"


def test_snapshot_from_payload_empty_payload():
    from bailoteca.cli import _snapshot_from_payload

    snap = _snapshot_from_payload({})
    assert snap.name == ""
    assert snap.urls == ()
    assert snap.phones == ()
    assert snap.address_texts == ()
    assert snap.comuna is None
