"""Operational failures whose recovery requires a durable checkpoint boundary."""


class BudgetExceeded(RuntimeError):
    """A finite admission, staging or outbox budget requires explicit backpressure."""


class CheckpointConflict(RuntimeError):
    """Another state owner changed the checkpoint; discard this engine and recover."""
