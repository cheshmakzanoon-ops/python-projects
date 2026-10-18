"""Framework-independent immutable accounting values."""

from dataclasses import dataclass
from uuid import UUID

from .money import EXPONENTS, MAX_AMOUNT


@dataclass(frozen=True)
class Entry:
    account_id: UUID
    amount: int


@dataclass(frozen=True)
class JournalValue:
    tenant_id: UUID
    currency: str
    entries: tuple[Entry, ...]
    reference: str = ""

    def validate(self) -> None:
        if self.currency not in EXPONENTS:
            raise ValueError("unsupported currency")
        if len(self.entries) < 2 or len(self.entries) > 256:
            raise ValueError("journal requires 2..256 postings")
        if any(
            type(e.amount) is not int or not 0 < abs(e.amount) <= MAX_AMOUNT for e in self.entries
        ):
            raise ValueError("invalid posting amount")
        if sum(e.amount for e in self.entries):
            raise ValueError("unbalanced journal")
        if len({e.account_id for e in self.entries}) != len(self.entries):
            raise ValueError("duplicate account")
        if len(self.reference) > 200:
            raise ValueError("reference too long")

    def reversed(self) -> "JournalValue":
        return JournalValue(
            self.tenant_id,
            self.currency,
            tuple(Entry(e.account_id, -e.amount) for e in self.entries),
            self.reference,
        )
