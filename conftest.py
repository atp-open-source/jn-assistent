"""
Root-pytest-konfiguration.

Springer automatisk tests over, der afhænger af miljøer, vi endnu ikke
har i CI:

- Windows-specifikke, native moduler (`pywin32`, `pyaudiowpatch`).
- Det eksterne `spark_core`-/`leverance.core`-framework beskrevet i
  PROGRESS.md.
- Tests der kræver tunge, valgfrie afhængigheder (fx `nltk`), der endnu
  ikke er i dev-gruppen.

Vi bruger `pytest_ignore_collect` frem for at markere indsamlede items,
så moduler, der fejler ved *import*, også springes rent over.

Når afhængighederne bliver tilgængelige, bliver disse predikater no-ops.
"""

from __future__ import annotations

import importlib.util
import os
import socket
import sys
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.resolve()


def _available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


WINDOWS = sys.platform.startswith("win")
HAS_SPARK_CORE = _available("spark_core")
HAS_LEVERANCE_CORE = _available("leverance.core")
HAS_NLTK = _available("nltk")
HAS_WIN32 = _available("win32gui")


def _env_flag(name: str) -> bool | None:
    value = os.getenv(name)
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return None


@lru_cache(maxsize=1)
def _business_db_target() -> tuple[str, int]:
    db_uri = os.getenv("LEVERANCE_BUSINESS_DATABASE_URI")
    if db_uri:
        try:
            from sqlalchemy.engine import make_url

            db_name = os.getenv("LEVERANCE_BUSINESS_DATABASE_NAME", "DFD_LEVERANCE_forretning")
            parsed = make_url(db_uri.format(db=db_name))
            return parsed.host or "", int(parsed.port or 1433)
        except Exception:
            pass

    host = os.getenv("LEVERANCE_SQL_HOST", os.getenv("SQLSERVER_HOST", "mssql"))
    port = int(os.getenv("LEVERANCE_SQL_PORT", os.getenv("SQLSERVER_PORT", "1433")))
    return host, port


@lru_cache(maxsize=1)
def _business_db_status() -> tuple[bool, str]:
    forced = _env_flag("JN_TEST_DB_AVAILABLE")
    if forced is False:
        return False, "JN_TEST_DB_AVAILABLE is disabled"

    if not _available("pyodbc"):
        return False, "pyodbc is not installed"

    if forced is True:
        return True, "JN_TEST_DB_AVAILABLE is enabled"

    host, port = _business_db_target()
    if not host:
        return False, "SQL Server host is not configured"

    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True, f"SQL Server reachable at {host}:{port}"
    except OSError as exc:
        return False, f"SQL Server is not reachable at {host}:{port} ({exc})"


def pytest_ignore_collect(collection_path, config):  # type: ignore[override]
    path = Path(str(collection_path)).resolve()
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        return False

    parts = rel.parts
    name = rel.name

    # audio_streamer-tests kræver pywin32 — springes over uden for Windows.
    if parts[:1] == ("tests",) and "audio_streamer" in name and not HAS_WIN32:
        return True

    # End-to-end-tests kræver Azure-credentials og netværk.
    if "end_to_end_and_load_test" in parts:
        return True

    # Leverance business component-tests kræver det eksterne framework.
    if parts[:1] == ("leverance",) and name.startswith("_test_"):
        if not (HAS_SPARK_CORE and HAS_LEVERANCE_CORE):
            return True
        # Text processor-testen kræver nltk.
        if "text_processor" in name and not HAS_NLTK:
            return True

    return False


def pytest_collection_modifyitems(config, items):
    db_available, reason = _business_db_status()
    if db_available:
        return

    skip_business_db = pytest.mark.skip(
        reason=f"JN business-component tests require a SQL Server test DB: {reason}"
    )
    for item in items:
        path = Path(str(item.path)).resolve()
        try:
            rel = path.relative_to(ROOT)
        except ValueError:
            continue

        if rel.parts[:1] == ("leverance",) and rel.name.startswith("_test_"):
            item.add_marker(skip_business_db)
