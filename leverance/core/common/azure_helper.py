from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

from aiservice.authentication import (
    Authentication as ClientSecretAuthentication,
)
from aiservice.authentication import (
    BaseAuthentication,
    ManagedIdentityAuthentication,
)
from spark_core.config.base_config import ConfigEnv


@dataclass
class _StaticAccessToken:
    token: str
    expires_on: int


class _StaticCredential:
    def __init__(self, token: str):
        self._token = token

    def get_token(self, _scope: str) -> _StaticAccessToken:
        return _StaticAccessToken(
            token=self._token,
            expires_on=int(time.time()) + 3600,
        )


class LocalDevelopmentAuthentication(BaseAuthentication):
    """Shim-auth der virker mod Azurite og mock-LLM i lokal tilstand."""

    def __init__(self, token: str | None = None):
        self._token = token or os.getenv("JN_LOCAL_TOKEN", "local-development-token")
        super().__init__()

    def _create_credential(self):
        return _StaticCredential(self._token)


def _read_keys_file(app) -> dict[str, Any]:
    try:
        with open(app.config.KEYS_AZURE, encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


def _is_local_mode() -> bool:
    return os.getenv("JN_LOCAL_MODE") == "1" or bool(os.getenv("AZURE_STORAGE_CONNECTION_STRING"))


def get_auth_based_on_env(app, **key_names) -> BaseAuthentication:
    """Returnerer auth-objekt kompatibelt med storage og OpenAI-klienterne."""

    if _is_local_mode():
        return LocalDevelopmentAuthentication()

    if app.config.ENVIRONMENT == ConfigEnv.AZURE_SERVER or app.config.NAME in {
        "azure",
        "azure-jn-dev",
        "azure-jn-prod",
    }:
        return ManagedIdentityAuthentication()

    keys = _read_keys_file(app)
    tenant_id = os.getenv(key_names.get("tenant_key_name", "")) or keys.get(
        key_names.get("tenant_key_name", "")
    )
    client_id = os.getenv(key_names.get("client_key_name", "")) or keys.get(
        key_names.get("client_key_name", "")
    )
    client_secret = os.getenv(key_names.get("secret_key_name", "")) or keys.get(
        key_names.get("secret_key_name", "")
    )
    return ClientSecretAuthentication(
        azure_identity_tenant_id=tenant_id,
        azure_identity_client_id=client_id,
        azure_identity_client_secret=client_secret,
    )


def get_openai_config_based_on_env(
    app,
    endpoint_key_name: str,
    version_key_name: str,
    deployment_key_name: str,
) -> tuple[str | None, str | None, str | None]:
    """Henter OpenAI-konfiguration fra env med JSON-fil som fallback."""

    keys = _read_keys_file(app)
    endpoint = os.getenv(endpoint_key_name) or keys.get(endpoint_key_name)
    version = os.getenv(version_key_name) or keys.get(version_key_name)
    deployment = os.getenv(deployment_key_name) or keys.get(deployment_key_name)
    return endpoint, version, deployment
