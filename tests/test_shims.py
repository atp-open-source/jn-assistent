from __future__ import annotations

import time
from types import SimpleNamespace

from leverance.core.common.timeout_handler import run_with_timeout
from leverance.core.logger_adapter import ServiceLoggerAdapter
from spark_core.app import App
from spark_core.components.core_types import OutputTable
from spark_core.config.base_config import Config
from spark_core.logger.logger import Logger


def test_config_callables_are_env_driven(monkeypatch):
    monkeypatch.setenv("LEVERANCE_BUSINESS_DATABASE_NAME", "leverance")
    monkeypatch.setenv(
        "LEVERANCE_BUSINESS_DATABASE_URI",
        "mssql+pyodbc://sa:Password123@test-db:1433/{db}?driver=ODBC+Driver+18+for+SQL+Server",
    )

    config = Config("local")

    assert config.LEVERANCE_BUSINESS_DATABASE_NAME() == "leverance"
    assert (
        config.LEVERANCE_BUSINESS_DATABASE_URI()
        == "mssql+pyodbc://sa:Password123@test-db:1433/leverance?driver=ODBC+Driver+18+for+SQL+Server"
    )


def test_app_exposes_config_and_log(monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_TO_FILE", "0")
    config = Config("local")
    config.LOGS_PATH = str(tmp_path)

    app = App(config=config, applikation="TEST_APP")

    assert app.config is config
    assert app.log is not None
    assert callable(app.log.info)


def test_service_logger_adapter_tolerates_component_message_and_kwargs(tmp_path):
    logger = Logger(
        log_directory=str(tmp_path),
        log_file="service.log",
        applikation="test",
        log_to_file=False,
    )
    adapter = ServiceLoggerAdapter(logger, request_uid="req-1")
    component = SimpleNamespace(get_component_name=lambda: "FakeComponent")

    adapter.service_info(component, "info", call_id="call-1")
    adapter.service_warning(component, "warning", process_time=0.1)
    adapter.service_exception(component, "exception", payload={"ok": True})

    assert adapter.request_uid == "req-1"
    assert adapter._component_name(component) == "FakeComponent"


def test_run_with_timeout_returns_result_before_timeout():
    class Worker:
        app = SimpleNamespace(log=None)

        @run_with_timeout(timeout=0.2, result_by_timeout="timeout")
        def work(self):
            return "done"

    assert Worker().work() == "done"


def test_run_with_timeout_returns_fallback_on_timeout():
    class Worker:
        app = SimpleNamespace(log=None)

        @run_with_timeout(timeout=0.01, result_by_timeout="timeout")
        def work(self):
            time.sleep(0.05)
            return "done"

    assert Worker().work() == "timeout"


def test_output_table_constructs_with_defaults():
    table = OutputTable("leverance", "jn", "notat")

    assert table.db == "leverance"
    assert table.schema == "jn"
    assert table.table == "notat"
    assert table.do_not_delete is False
    assert table.index_columns == []
