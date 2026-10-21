"""
Helpers for tests that race real database transactions against each
other.

These only mean something on Postgres: SQLite serializes writers and
ignores `select_for_update`, so a "race" there proves nothing. Use
`requires_postgres` on any TransactionTestCase that relies on
`run_concurrently`.
"""

from __future__ import annotations

import threading
import unittest

from django.db import connection, connections


def requires_postgres(test_item):
    return unittest.skipUnless(
        connection.vendor == "postgresql", "concurrency test needs Postgres (SQLite serializes writers)"
    )(test_item)


def run_concurrently(*callables, timeout: float = 30.0) -> list:
    """Start every callable at the same moment, each in its own thread
    with its own DB connection, and return one outcome per callable:
    its return value, or the exception it raised."""
    barrier = threading.Barrier(len(callables))
    outcomes: list = [None] * len(callables)

    def worker(index, fn):
        try:
            barrier.wait(timeout=timeout)
            outcomes[index] = fn()
        except BaseException as exc:  # noqa: BLE001 — reported back to the test
            outcomes[index] = exc
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker, args=(i, fn)) for i, fn in enumerate(callables)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=timeout)
        if thread.is_alive():
            raise AssertionError("concurrent worker did not finish (possible deadlock)")
    return outcomes
