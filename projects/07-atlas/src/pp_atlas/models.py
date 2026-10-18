"""Public immutable product records."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Document:
    id: str
    title: str
    text: str
    acl: frozenset[str] = frozenset({"*"})
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or len(self.id) > 256 or len(self.title) > 1024:
            raise ValueError("invalid document id/title")
        if any(not value or len(value) > 256 for value in self.acl):
            raise ValueError("invalid ACL subject")
        if len(self.acl) > 128 or len(self.metadata) > 32:
            raise ValueError("ACL/metadata exceeds limit")
        if any(len(k) > 64 or len(v) > 4096 for k, v in self.metadata.items()):
            raise ValueError("metadata exceeds limit")


@dataclass(frozen=True)
class Hit:
    id: str
    revision: str
    title: str
    score: float
    snippet: str
    explanation: dict[str, float]


@dataclass(frozen=True)
class SearchResult:
    generation: int
    acl_revision: int
    total: int
    hits: tuple[Hit, ...]
    facets: dict[str, int]
    visible_documents: int
    statistics: dict[str, object] = field(default_factory=dict)
