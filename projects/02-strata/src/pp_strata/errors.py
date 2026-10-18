"""Explicit failures forming the public API contract."""


class StrataError(Exception):
    """Storage failure."""


class Corruption(StrataError):
    """A complete persisted structure failed validation."""


class Conflict(StrataError):
    """A written key changed after the transaction snapshot."""


class OwnerBusy(StrataError):
    """Another handle/process owns the database."""


class WriterFailed(StrataError):
    """Uncertain persistence state requires close and recovery."""


class Closed(StrataError):
    """The database or snapshot has been closed."""
