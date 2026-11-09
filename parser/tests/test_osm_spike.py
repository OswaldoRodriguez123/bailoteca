import json
from pathlib import Path

from bailoteca.osm_spike import summarize
from bailoteca.sources.osm import parse_overpass


def test_summarize_counts_fields():
    data = json.loads(
        (Path(__file__).parent / "fixtures" / "overpass.json").read_text()
    )
    summary = summarize(parse_overpass(data))
    assert summary == {
        "named": 1,
        "with_address": 1,
        "with_web_or_ig": 1,
        "comunas": {"Providencia": 1},
    }
