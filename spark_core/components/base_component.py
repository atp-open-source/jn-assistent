"""
Dette modul indeholder base klassen, som alle komponenter,
på tværs af alle repos, arver fra.
"""

from __future__ import annotations

from abc import ABC
from typing import Any, Dict, List, Literal

from sqlalchemy import Connection, Result
from sqlalchemy.orm import Session

from spark_core.app import App
from spark_core.database.db_utils import execute_sql


class BaseComponent(ABC):
    """
    Abstrakt base klasse for alle komponenter.
    """

    def __init__(self, app: App, session: Session = None):
        self.app = app
        self.session = session

        # Bruges til at definere databaseforbindelsen
        self.server = "default"
        self.db_group = "default"

        # Bruges altid til at definere hovedtabellen for komponenten
        self.db = None
        self.schema = None
        self.table = None

        # Bruges hvis komponenten har flere tabeller, den skriver til
        self.output_tables = None

        # Bruges til at definere input argumenter til SQLAlchemy engine
        self.engine_kwargs = {"fast_executemany": True}

        # Bruges til unikke navne for temp tabeller
        self.temp_prefix = self.get_component_name()

    @classmethod
    def get_component_name(cls):
        return cls.__name__

    def create_sql(self, mode="batch"):
        """
        Opret SQL for komponenten.
        """
        raise NotImplementedError("Denne komponent bruger ikke SQL.")

    def execute_all(self):
        """
        Kør komponenten.
        """
        raise NotImplementedError(
            "Denne komponent understøtter ikke kørsel i batch-tilstand."
        )

    def execute_for_training(self):
        """
        Kør komponentens træning.
        """
        raise NotImplementedError("Denne komponent understøtter ikke træning.")

    def execute_sql(
        self, sql: str, executor: Session | Connection = None, *args, **kwargs
    ) -> Result:
        """
        Eksekverer et SQL-statement med den givne session eller forbindelse og returnerer resultatet.

        ## Parametre
        - `sql`: SQL-statement der skal eksekveres
        - `executor`: SQLAlchemy-session eller -forbindelse, der skal eksekvere SQL-statementet.
          Hvis denne er `None`, bruges i stedet `self.session`.
        - `*args`: Valgfri argumenter der skal sendes til `executor.execute()`
        - `**kwargs`: Valgfri keyword-argumenter der skal sendes til `executor.execute()`
        """
        return execute_sql(sql, executor or self.session, *args, **kwargs)

    def lookup_for_service(
        self,
        session: Session,
        input_dict: Dict[str, List[Any]],
        output_column_list: List[str],
        condition: str = None,
        format: Literal["dict", "DataFrame"] = "DataFrame",
    ):
        """
        Metode til at udføre SELECT statement på {self.db}.{self.schema}.{self.table}
        med potentielle betingelser.

        ## Parametre
        `session`: SQLAlchemy session

        `input_dict`: Dictionary med præcis ét nøgle-værdi par, hvor nøglen er en kolonne
        fra {self.db}.{self.schema}.{self.table} og hvor værdien er en liste af elementer,
        som data skal hentes for. NULL-værdier er ikke tilladt.

        `output_column_list`: Liste over kolonnenavne til at hente data for fra {self.db}.{self.schema}.{self.table}

        `condition`: String med valgfri WHERE-klausul til SELECT-sætningen

        `format`: Output format, vælg mellem følgende:
        * "dict": Returnerer resultatet som en ordbog
        * "DataFrame": Returnerer resultatet som en pandas DataFrame

        ## Returnerer
        Dict eller DataFrame afhængigt af formatet specificeret i input. Returnerer en tom
        datastruktur med korrekte kolonner, hvis der ikke er nogen match i tabellen.

        ## Kaster
        * ValueError hvis input er ugyldigt.
        """

        import pandas as pd

        self.session = session

        # Input kolonne og matchende værdier
        column = list(input_dict.keys())
        values = list(input_dict.values())

        # Tjekker at data kun anmodes for en enkelt kolonne
        if len(column) != 1 or type(values[0]) != list:
            raise ValueError(
                f"Ugyldigt input ved lookup_for_service for {self.db}.{self.schema}.{self.table}"
            )

        # Tager unikke værdier, der ikke er NULL, og tjekker at der er værdier tilbage
        data = [val for val in set(values[0]) if val is not None]
        if len(data) == 0:
            raise ValueError(
                f"Ugyldigt input ved lookup_for_service for {self.db}.{self.schema}.{self.table}"
            )

        # Tjekker at der er mindst én output kolonne
        if len(output_column_list) < 1:
            raise ValueError(
                f"Ugyldigt input ved lookup_for_service for {self.db}.{self.schema}.{self.table}"
            )

        # Konverterer strenge til værdier med indkapslede anførselstegn
        data = [f"'{val}'" if isinstance(val, str) else val for val in data]

        # Opret SQL query
        sql_to_execute = f"""
            SELECT
                {', '.join(output_column_list)}
            FROM {self.db}.{self.schema}.{self.table}
            WHERE {column[0]} IN ({', '.join(str(d) for d in data)})
        """

        # Tilføj en mulig WHERE-clause
        if condition is not None:
            sql_to_execute += f"AND ({condition})"

        # Udfør SQL query
        result = pd.read_sql(sql_to_execute, self.session.connection())

        # Returner resultatet i det korrekte format
        if format == "DataFrame":
            return result
        elif format == "dict":
            return result.to_dict(orient="list")

        raise ValueError(f"Ukendt format: {format}")


class NonSessionComponent(BaseComponent):
    """
    Abstrakt base klasse for komponenter, der ikke kræver en databaseforbindelse som input.
    """

    def __init__(self, app: App):
        super().__init__(app)
