from __future__ import annotations

from abc import ABC
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Literal

import sqlalchemy
from sqlalchemy import Connection, Result, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from spark_core.app import App
from spark_core.config.base_config import Config, get_project_config
from spark_core.database.db_utils import execute_sql, use_access_token_for_azure_sql


class ServiceRunner(ABC):
    """Minimal shim af leverance.core.runners.ServiceRunner."""

    def __init__(
        self,
        service_name,
        request_uid=None,
        config_overwrite=None,
        config_name=None,
        db_server_name="default",
        db_group_name="default",
    ):
        self.service_name = service_name
        self.request_uid = request_uid

        if config_overwrite is not None:
            config = config_overwrite
        elif isinstance(config_name, Config) or hasattr(config_name, "LEVERANCE_BUSINESS_DATABASE_URI"):
            config = config_name
        else:
            config = get_project_config(environment=config_name)

        self.app = App(
            config=config,
            applikation=f"SERVICE_{service_name}",
            use_db_server=db_server_name,
            use_db_group=db_group_name,
        )

        db_uri = self.app.config.LEVERANCE_BUSINESS_DATABASE_URI(db_server_name, db_group_name)
        self.engine = create_engine(
            db_uri,
            echo=False,
            poolclass=NullPool,
        )
        if "database.windows.net" in str(self.engine.url.host):
            use_access_token_for_azure_sql(self.engine)
        self.sessionfactory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.session = self.sessionfactory()
        self.sessions = {}
        self.threadpool = ThreadPoolExecutor(max_workers=self.app.config.NUM_THREADS_SERVICE)

    @classmethod
    def get_component_name(cls):
        return cls.__name__

    def __del__(self):
        try:
            if getattr(self, "session", None) is not None:
                self.session.close()
            for session in list(getattr(self, "sessions", {}).values()):
                session.close()
            if getattr(self, "engine", None) is not None:
                self.engine.dispose()
            if getattr(self, "threadpool", None) is not None:
                self.threadpool.shutdown(wait=False)
        except (KeyError, AttributeError, sqlalchemy.exc.ProgrammingError):
            pass

    def execute_sql(
        self, sql: str, executor: Session | Connection = None, *args, **kwargs
    ) -> Result:
        return execute_sql(sql, executor or self.session, *args, **kwargs)

    def submit_job(self, func, *args, session=True, **kwargs):
        if session:
            job_session = self.sessionfactory()
            future = self.threadpool.submit(func, job_session, *args, **kwargs)
            self.sessions[future] = job_session
            future.add_done_callback(self._close_session)
        else:
            future = self.threadpool.submit(func, *args, **kwargs)
        return future

    def _close_session(self, future):
        session = self.sessions.pop(future, None)
        if session is not None:
            session.close()

    def lookup_for_service(
        self,
        session: Session,
        input_dict: Dict[str, List[Any]],
        output_column_list: List[str],
        condition: str = None,
        format: Literal["dict", "DataFrame"] = "DataFrame",
    ):
        import pandas as pd

        self.session = session
        column = list(input_dict.keys())
        values = list(input_dict.values())

        if len(column) != 1 or type(values[0]) != list:
            raise ValueError(
                f"Ugyldigt input ved lookup_for_service for {self.db}.{self.schema}.{self.table}"
            )

        data = [val for val in set(values[0]) if val is not None]
        if len(data) == 0:
            raise ValueError(
                f"Ugyldigt input ved lookup_for_service for {self.db}.{self.schema}.{self.table}"
            )

        if len(output_column_list) < 1:
            raise ValueError(
                f"Ugyldigt input ved lookup_for_service for {self.db}.{self.schema}.{self.table}"
            )

        data = [f"'{val}'" if isinstance(val, str) else val for val in data]
        sql_to_execute = f"""
            SELECT
                {', '.join(output_column_list)}
            FROM {self.db}.{self.schema}.{self.table}
            WHERE {column[0]} IN ({', '.join(str(d) for d in data)})
        """

        if condition is not None:
            sql_to_execute += f"AND ({condition})"

        result = pd.read_sql(sql_to_execute, self.session.connection())
        if format == "DataFrame":
            return result
        if format == "dict":
            return result.to_dict(orient="list")
        raise ValueError(f"Ukendt format: {format}")
