"""
Custom typer, der kan bruges på tværs af alle projekter der bruger spark_core.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import get_type_hints


@dataclass
class OutputTable:
    db: str
    schema: str
    table: str
    pk: str = None
    conditions: str = None
    do_not_delete: bool = False
    deltaloaded: bool = False
    next_sanitize_date: date = None
    component_name: str = None
    audit_id_table: str = None
    index_columns: list = field(default_factory=lambda: [])
    rows_before_run: int = 0


def check_types(function: Callable):
    """
    Decorator, der bruger type-hints til at verificere funktionens input datatyper.
    """

    def checker(*args, **kwargs):
        hints = get_type_hints(function)

        all_variables = kwargs.copy()
        all_variables.update(dict(zip(function.__code__.co_varnames, args, strict=False)))

        for name, value in all_variables.items():
            if name not in hints:
                continue

            if not issubclass(type(value), hints[name]):
                raise TypeError(
                    f"{name} er type: '{type(value).__name__}' og burde have været type: '{hints[name].__name__}'"
                )

        output = function(*args, **kwargs)

        if "return" in hints and not issubclass(type(output), hints["return"]):
            raise TypeError(
                f"Output er type: '{type(output).__name__}' og burde have været type: '{hints['return'].__name__}'"
            )

        return output

    return checker


class NonSqlStatement:
    """
    Dekorator til brug for funktionskald, der ikke er SQL statements.
    Denne dekorator sikrer, at 'print query'-kommandoen
    kan håndtere ikke-SQL-statements.
    """

    def __init__(self, arg):
        self._arg = arg

    def __call__(self, outer_self):
        return self._arg(outer_self)

    def __str__(self):
        kommentar = (
            "\n/*** HER KØRES EN IKKE-SQL STATEMENT. DEN KALDTE FUNKTION ER: SE FUNKTIONEN KALDT I def "
            + self._arg.__name__
            + " ***/\n"
        )
        return kommentar


class ComponentRunStatus(Enum):
    """
    Statuskoder for komponenter under en kørsel, så vi kan holde styr på
    hvilke komponenter der er blevet udført og hvilke der er fejlet.
    """

    NOT_RUN = 0
    RUNNING = 1
    RUN_SUCCESSFULLY = 2
    FAILED = 3
    DEPENDENCY_FAILED = 4
    PENDING = 5
