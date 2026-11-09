from dataclasses import dataclass, field


@dataclass(frozen=True)
class Candidate:
    name: str
    url: str | None
    handle: str | None
    source: str
    comuna: str | None = None
    raw: dict = field(default_factory=dict)
