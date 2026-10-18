"""Run after installing the wheel: python catalog.py /absolute/new-database."""

import sys

from pp_strata import Database

with Database.open(sys.argv[1]) as database:
    with database.begin() as transaction:
        transaction.put(b"catalog:001", b"first edition")
    with database.snapshot() as historical:
        with database.begin() as transaction:
            transaction.put(b"catalog:001", b"second edition")
        database.compact()
        assert historical.get(b"catalog:001") == b"first edition"
        print(list(historical.scan(start=b"catalog:", stop=b"catalog;")))
