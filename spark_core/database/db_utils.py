from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine, Result, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session


@dataclass
class _BufferedResult:
    keys_list: list[str]
    rows: list[Any]

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)

    def first(self):
        return self.fetchone()

    def keys(self):
        return list(self.keys_list)

    def __iter__(self) -> Iterator[Any]:
        return iter(self.rows)


def execute_sql(*args: Any, params: dict[str, Any] | None = None, **kwargs: Any) -> Result | _BufferedResult:
    """Eksekver SQL mod Session, Connection eller Engine.

    Understøtter både signaturen `(sql, executor, ...)` og den mere direkte
    `(executor, sql, params=None)` for shim-kompatibilitet.
    """

    if len(args) < 2:
        raise TypeError("execute_sql kræver både executor og sql")

    if isinstance(args[0], str):
        sql = args[0]
        executor = args[1]
        rest = args[2:]
    else:
        executor = args[0]
        sql = args[1]
        rest = args[2:]

    statement = text(sql)

    if isinstance(executor, Engine):
        with executor.begin() as connection:
            result = connection.execute(statement, params or {}, *rest, **kwargs)
            if result.returns_rows:
                return _BufferedResult(list(result.keys()), result.fetchall())
            return _BufferedResult([], [])

    if isinstance(executor, Session):
        return executor.execute(statement, params or {}, *rest, **kwargs)

    if isinstance(executor, Connection):
        return executor.execute(statement, params or {}, *rest, **kwargs)

    raise TypeError(f"Ugyldig executor type: {type(executor)!r}")


def use_access_token_for_azure_sql(*_args: Any, **_kwargs: Any) -> None:
    """No-op shim. Prod-auth håndteres udenfor denne repo-shim."""

    return None
