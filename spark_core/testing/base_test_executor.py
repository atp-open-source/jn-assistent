from __future__ import annotations

import inspect
import os
import random
from datetime import date, datetime
from typing import Any

import sqlalchemy
from sqlalchemy import DateTime, Engine, create_engine, delete, insert
from sqlalchemy.dialects.mssql import DATETIME, DATETIME2
from sqlalchemy.orm import Session, sessionmaker

from spark_core.app import App
from spark_core.components.base_component import BaseComponent
from spark_core.components.core_types import OutputTable
from spark_core.config.base_config import Config, get_project_config
from spark_core.database.db_utils import execute_sql


class DbSession:
    """Lille wrapper omkring SQLAlchemy session brugt i tests."""

    tabletype = sqlalchemy.Table
    classtype = sqlalchemy.orm.DeclarativeBase

    def __init__(self, dburl: str):
        self.dburl = dburl
        self.engine: Engine = create_engine(self.dburl)
        self.session: Session = sessionmaker(bind=self.engine, expire_on_commit=False)()

    def close(self) -> None:
        self.session.close()
        self.engine.dispose()

    def execute_sql(self, sql: str, executor: Session | None = None, *args: Any, **kwargs: Any):
        return execute_sql(sql, executor or self.session, *args, **kwargs)

    def insert_into_table(self, table, columns_dict: dict[str, Any] | None = None, **kwargs: Any):
        data = columns_dict or kwargs
        if not data:
            raise AssertionError("Der kom ikke nogen værdier med, som skulle indsættes")

        patched = dict(data)
        for key, value in list(patched.items()):
            if not isinstance(value, date) or isinstance(value, datetime):
                continue
            try:
                column = getattr(table, key) if inspect.isclass(table) else table.c[key]
                if isinstance(column.type, DateTime | DATETIME | DATETIME2):
                    patched[key] = datetime(value.year, value.month, value.day)
            except Exception:  # noqa: S112 - bedste forsøg på dato-konvertering; spring fejlende kolonner over
                continue

        self.session.execute(insert(table).values(patched))
        self.session.commit()

    def delete_from_table(self, table):
        self.session.execute(delete(table))
        self.session.commit()


class BaseTestExecutor:
    """Minimal test harness mod SQL Server-testdatabasen."""

    def __init__(self):
        self.config: Config = get_project_config()
        self.app = App(self.config, "test")

        business_uri = self.config.LEVERANCE_BUSINESS_DATABASE_URI()
        self.db_leverance = DbSession(business_uri)
        self.db_dfd_leverance_forretning = DbSession(business_uri)
        self.db_dfd_spark_bestand = DbSession(
            self.config.create_dburi(
                os.getenv(
                    "DFD_SPARK_BESTAND_DATABASE_NAME",
                    self.config.LEVERANCE_BUSINESS_DATABASE_NAME(),
                )
            )
        )
        self.db_dfd_spark_kilde = DbSession(
            self.config.create_dburi(
                os.getenv(
                    "DFD_SPARK_KILDE_DATABASE_NAME", self.config.LEVERANCE_BUSINESS_DATABASE_NAME()
                )
            )
        )
        self.db_main = self.db_leverance
        self.snapshot_uid = None

    def execute_component(self, component):
        if isinstance(component, type) and issubclass(component, BaseComponent):
            component = component(request_uid="test")
        return component.execute_all()

    def execute_component_for_service(
        self, component_cls: type[BaseComponent], method: str, *args: Any
    ):
        component = component_cls(request_uid="test", config_name=self.config.NAME)
        component.session = self.db_leverance.session
        return getattr(component, method)(*args)

    def delete_output_tables(self, component_cls: type[BaseComponent]):
        component = component_cls(request_uid="test", config_name=self.config.NAME)
        component.session = self.db_leverance.session

        output_tables = []
        if getattr(component, "output_tables", None) is None:
            output_tables.append(OutputTable(component.db, component.schema, component.table))
        else:
            for output_table in component.output_tables:
                if isinstance(output_table, OutputTable):
                    output_tables.append(output_table)
                else:
                    output_tables.append(OutputTable(*output_table))

        for table in output_tables:
            if not table.db or not table.schema or not table.table or table.do_not_delete:
                continue
            sql = f"TRUNCATE TABLE {table.db}.{table.schema}.{table.table}"
            if table.conditions:
                sql = (
                    f"DELETE FROM {table.db}.{table.schema}.{table.table} "  # noqa: S608 - testoprydning fra betroet tabel-metadata
                    f"WHERE {table.conditions}"
                )
            try:
                self.db_leverance.execute_sql(sql)
            except Exception:
                self.db_leverance.execute_sql(
                    f"DELETE FROM {table.db}.{table.schema}.{table.table}"  # noqa: S608 - testoprydning fra betroet tabel-metadata
                )
        self.db_leverance.session.commit()

    def drop_temp_tables(self):
        self.db_main.session.commit()
        execute_sql(
            self.db_main.session,
            """
            DECLARE @d_sql NVARCHAR(MAX)
            SET @d_sql = ''

            SELECT @d_sql = @d_sql + 'DROP TABLE ' + QUOTENAME(name) + ';'
            FROM tempdb..sysobjects
            WHERE name LIKE '#[^#]%'
                AND OBJECT_ID('tempdb..'+QUOTENAME(name)) IS NOT NULL

            IF @d_sql <> ''
            BEGIN
                EXEC(@d_sql)
            END
            """,
        )
        self.db_main.session.commit()

    def __enter__(self):
        random.seed(42)
        return self

    def __exit__(self, _type, _value, _traceback):
        for db in (
            self.db_leverance,
            self.db_dfd_leverance_forretning,
            self.db_dfd_spark_bestand,
            self.db_dfd_spark_kilde,
        ):
            db.close()
        random.seed(0)
