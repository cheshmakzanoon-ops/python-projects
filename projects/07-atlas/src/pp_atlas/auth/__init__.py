"""Principal values must originate in an authenticated adapter, never request groups."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    tenant: str
    subject: str

    def __post_init__(self) -> None:
        if not self.tenant or not self.subject or len(self.tenant) > 256 or len(self.subject) > 256:
            raise ValueError("invalid tenant or subject")
