"""The library's own database (eaxlibrary, schema lib): one connection per request, committed when the request ends."""

from __future__ import annotations

from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from .config import get_settings


@contextmanager
def connect():
    """A connection to the library's database (rows as dicts), committed at the end."""
    with psycopg.connect(get_settings().dsn(), row_factory=dict_row, autocommit=False) as conn:
        yield conn


def rows(conn, sql: str, **p) -> list[dict]:
    """Rows of a query."""
    return list(conn.execute(sql, p).fetchall())


def one(conn, sql: str, **p) -> dict | None:
    """One row of a query, or None."""
    return conn.execute(sql, p).fetchone()
