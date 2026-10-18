from uuid import UUID

from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from pp_meridian.domain.journal import Entry, JournalValue
from pp_meridian.domain.replay import HistoricalPosting, replay, trial_balance


class LedgerHistoryModel(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.tenant = UUID(int=1)
        self.a, self.b = UUID(int=2), UUID(int=3)
        self.rows = []
        self.expected = []
        self.total = 0
        self.sequence = 0
        self.originals = []

    def append(self, amount):
        self.sequence += 1
        value = JournalValue(self.tenant, "USD", (Entry(self.a, amount), Entry(self.b, -amount)))
        value.validate()
        self.rows.extend(
            [HistoricalPosting(e.account_id, "USD", e.amount, self.sequence) for e in value.entries]
        )
        self.total += amount
        self.expected.append(self.total)

    @rule(amount=st.integers(-(10**9), 10**9).filter(bool))
    def post(self, amount):
        self.append(amount)
        self.originals.append(amount)

    @rule()
    def reverse_original(self):
        if self.originals:
            self.append(-self.originals.pop())

    @invariant()
    def every_historical_prefix_matches_independent_model(self):
        assert trial_balance(self.rows) in ({}, {"USD": 0})
        for sequence, amount in enumerate(self.expected, 1):
            assert replay(self.rows, sequence) == {self.a: amount, self.b: -amount}


TestLedgerHistoryModel = LedgerHistoryModel.TestCase
TestLedgerHistoryModel.settings = settings(max_examples=25, stateful_step_count=35, deadline=None)
