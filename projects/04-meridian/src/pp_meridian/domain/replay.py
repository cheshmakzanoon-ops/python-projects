"""Independent fold of immutable posting history; no projection reads."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class HistoricalPosting:
    account_id: UUID
    currency: str
    amount: int
    sequence: int


def replay(postings: Iterable[HistoricalPosting], as_of: int | None = None) -> dict[UUID, int]:
    balances: dict[UUID, int] = defaultdict(int)
    for posting in postings:
        if as_of is None or posting.sequence <= as_of:
            balances[posting.account_id] += posting.amount
    return dict(balances)


def trial_balance(postings: Iterable[HistoricalPosting]) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for posting in postings:
        totals[posting.currency] += posting.amount
    return dict(totals)
