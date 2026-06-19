from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus


class ConfigEnv(Enum):
    """Miljøer brugt af de rigtige frameworks."""

    LOCAL = "local"
    DEV = "dev"
    DEV_SERVER = "dev-server"
    TEST_SERVER = "test-server"
    PROD_SERVER = "prod-server"
    TEST = "test"
    AZURE_SERVER = "azure"


class Config:
    """Minimal miljødrevet shim-konfiguration til JN-assistent."""

    _AZURE_NAMES = {"azure", "azure-jn-dev", "azure-jn-prod"}

    def __init__(self, environment: str | ConfigEnv | None = None):
        base_dir = Path(__file__).resolve().parent

        env_name = environment.value if isinstance(environment, ConfigEnv) else environment
        env_name = env_name or os.getenv("SPARK_CONFIG") or os.getenv("ENVIRONMENT") or "local"

        self.NAME = str(env_name)
        self.ENVIRONMENT = self._resolve_environment(self.NAME)
        self.NUM_THREADS_SERVICE = int(os.getenv("NUM_THREADS_SERVICE", "4"))

        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_TO_FILE = os.getenv("LOG_TO_FILE", "0") == "1"
        self.LOGS_PATH = os.getenv("LOGS_PATH", str(Path.cwd() / "log"))

        self.LEVERANCE_BUSINESS_DB_NAME = os.getenv(
            "LEVERANCE_BUSINESS_DATABASE_NAME", "DFD_LEVERANCE_forretning"
        )
        self._leverance_business_db_uri = os.getenv("LEVERANCE_BUSINESS_DATABASE_URI")

        self.DB_DRIVER = os.getenv("LEVERANCE_SQL_DRIVER", "ODBC Driver 18 for SQL Server")
        self.DB_HOST = os.getenv("LEVERANCE_SQL_HOST", os.getenv("SQLSERVER_HOST", "mssql"))
        self.DB_PORT = int(os.getenv("LEVERANCE_SQL_PORT", os.getenv("SQLSERVER_PORT", "1433")))
        self.DB_USER = os.getenv("LEVERANCE_SQL_USER", os.getenv("SQLSERVER_USER", "sa"))
        self.DB_PASSWORD = os.getenv(
            "LEVERANCE_SQL_PASSWORD",
            os.getenv("SQLSERVER_PASSWORD", "YourStrong!Passw0rd"),
        )
        self.DB_TRUST_SERVER_CERTIFICATE = os.getenv(
            "LEVERANCE_SQL_TRUST_SERVER_CERTIFICATE", "yes"
        )

        self.JN_AZURE_STORAGE_ACCOUNT = os.getenv(
            "JN_AZURE_STORAGE_ACCOUNT", "devstoreaccount1"
        )
        self.KEYS_AZURE = os.getenv(
            "KEYS_AZURE",
            str(base_dir / "keys_azure.local.json"),
        )

        self.JN_INTERACTION_READ_AD = os.getenv("JN_INTERACTION_READ_AD", "JN_INTERACTION_READ_AD")
        self.JN_INTERACTION_TITLE = os.getenv("JN_INTERACTION_TITLE", "JN-assistent")
        self.JN_NOTATER_READ_AD = os.getenv("JN_NOTATER_READ_AD", "JN_NOTATER_READ_AD")

        self.JN_AZURE_OPENAI_API_ENDPOINT = os.getenv(
            "JN_AZURE_OPENAI_API_ENDPOINT", "http://mock-llm:8000"
        )
        self.JN_AZURE_OPENAI_API_VERSION = os.getenv(
            "JN_AZURE_OPENAI_API_VERSION", "2024-10-21"
        )
        self.JN_AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv(
            "JN_AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"
        )

    @staticmethod
    def _resolve_environment(name: str) -> ConfigEnv:
        lowered = name.lower()
        if lowered in Config._AZURE_NAMES:
            return ConfigEnv.AZURE_SERVER
        for env in ConfigEnv:
            if lowered in {env.name.lower().replace("_", "-"), env.value.lower()}:
                return env
        return ConfigEnv.LOCAL

    def is_environment(self, *environments: ConfigEnv | str) -> bool:
        for env in environments:
            if isinstance(env, ConfigEnv) and self.ENVIRONMENT == env:
                return True
            if isinstance(env, str):
                lowered = env.lower()
                if lowered in {
                    self.ENVIRONMENT.name.lower().replace("_", "-"),
                    self.ENVIRONMENT.value.lower(),
                    self.NAME.lower(),
                }:
                    return True
        return False

    def create_dburi(self, db_name: str | None = None) -> str:
        if self._leverance_business_db_uri:
            if "{db}" in self._leverance_business_db_uri and db_name:
                return self._leverance_business_db_uri.format(db=db_name)
            return self._leverance_business_db_uri

        database = db_name or self.LEVERANCE_BUSINESS_DB_NAME
        password = quote_plus(self.DB_PASSWORD)
        driver = quote_plus(self.DB_DRIVER)
        return (
            f"mssql+pyodbc://{self.DB_USER}:{password}@{self.DB_HOST}:{self.DB_PORT}/"
            f"{database}?driver={driver}&TrustServerCertificate={self.DB_TRUST_SERVER_CERTIFICATE}"
        )

    def LEVERANCE_BUSINESS_DATABASE_NAME(self, *_args: Any, **_kwargs: Any) -> str:
        return self.LEVERANCE_BUSINESS_DB_NAME

    def LEVERANCE_BUSINESS_DATABASE_URI(self, *_args: Any, **_kwargs: Any) -> str:
        return self.create_dburi(self.LEVERANCE_BUSINESS_DB_NAME)


BaseConfig = Config


def get_project_config(environment: str | ConfigEnv | None = None) -> Config:
    return Config(environment=environment)


def get_core_config(environment: str | ConfigEnv | None = None) -> Config:
    return Config(environment=environment)


def get_config(*_args: Any, environment: str | ConfigEnv | None = None, **_kwargs: Any) -> Config:
    return Config(environment=environment)
