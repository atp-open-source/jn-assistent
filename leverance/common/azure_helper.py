import json
import os

from dfd_azure_ml.core.clients.azure_blob_client import AzureBlobClient
from dfd_azure_ml.core.clients.ml_auth_client import Authentication
from ork.project_handler import get_config_for_project
from spark_core.database.db_utils import use_access_token_for_azure_sql
from sqlalchemy import Engine, create_engine

from aiservice.authentication import (
    Authentication as clientSecretAuthentication,
)
from aiservice.authentication import (
    BaseAuthentication,
    ManagedIdentityAuthentication,
)


def create_azure_blob_client(app, category, container, account_name):
    """
    Initializes the AzureBlobClient and returns the instance.
    """
    try:
        with open(app.config.KEYS_AZURE) as f:
            keys = json.load(f)

        tenant_id = keys.get("DA_SPARK_AZURE_IDENTITY_TENANT_ID", None)
        client_id = keys.get("DA_SPARK_AZURE_IDENTITY_CLIENT_ID", None)
        client_secret = keys.get("DA_SPARK_AZURE_IDENTITY_CLIENT_SECRET", None)
    except Exception as e:
        app.log.error(f"Fejl i at finde keys til azure: {e}")
        tenant_id = client_id = client_secret = None

    container_name = f"{category}-{container}"
    return AzureBlobClient(
        account_name=account_name,
        container_name=container_name,
        auth=Authentication(
            azure_identity_tenant_id=tenant_id,
            azure_identity_client_id=client_id,
            azure_identity_client_secret=client_secret,
        ),
    )


def get_auth_based_on_env(
    app, tenant_key_name: str, client_key_name: str, secret_key_name: str
) -> BaseAuthentication:
    """
    Hjælpefunktion til at oprette et BaseAuthentication-objekt til at authenticate mod
    Azure. Henter en ManagedIdentityAuthentication-objekt, hvis vi kører i et Azure-
    miljø. Ellers laves et ClientSecret-baseret Authentication-objekt ud fra nøgler
    i en konfigurationsfil.

    Args:
        app: app-objektet, hvorfra miljøet kan hentes fra config.
        tenant_key_name: navnet på tenant-id nøglen i config-filen
        client_key_name: navnet på client-id nøglen i config-filen
        secret_key_name: navnet på client-secret nøglen i config-filen

    Returns:
        BaseAuthentication: et Authentication-objekt til at authenticate mod Azure.
    """
    # Hen authentication baseret på config-miljø
    if app.config.NAME in ("azure", "azure-jn-dev", "azure-jn-prod"):
        # Initialisér ManagedIdentityAuthentication-objekt
        authentication = ManagedIdentityAuthentication()
    else:
        with open(app.config.KEYS_AZURE) as f:
            keys = json.load(f)
            tenant_id = keys.get(tenant_key_name)
            client_id = keys.get(client_key_name)
            client_secret = keys.get(secret_key_name)

            # Initialisér Authentication-objekt
            authentication = clientSecretAuthentication(
                azure_identity_tenant_id=tenant_id,
                azure_identity_client_id=client_id,
                azure_identity_client_secret=client_secret,
            )

    return authentication


def get_openai_config_based_on_env(
    app,
    endpoint_key_name: str,
    version_key_name: str,
    deployment_key_name: str,
) -> tuple[str, str, str]:
    """
    Hjælpefunktion til at hente OpenAI konfigurationsværdier baseret på miljøet.

    Args:
        app: app-objektet, hvorfra miljøet kan hentes fra config.
        endpoint_key_name: navnet på endpoint-nøglen i config-filen
        version_key_name: navnet på version-nøglen i config-filen
        deployment_key_name: navnet på deployment-nøglen i config-filen

    Returns:
        tuple[str, str, str]: en tuple med endpoint, version og deployment navn.
    """
    if app.config.NAME in ("azure", "azure-jn-dev", "azure-jn-prod"):
        endpoint = os.getenv(endpoint_key_name)
        version = os.getenv(version_key_name)
        deployment = os.getenv(deployment_key_name)
    else:
        with open(app.config.KEYS_AZURE) as f:
            keys = json.load(f)
            endpoint = keys.get(endpoint_key_name)
            version = keys.get(version_key_name)
            deployment = keys.get(deployment_key_name)

    return endpoint, version, deployment


def opret_azure_engine(app) -> Engine:
    """
    Opretter en SQLAlchemy engine til Azure SQL med korrekt konfiguration og authentication.
    Bruger service principal authentication via miljøvariabler.
    """
    try:
        # Hent target miljø fra miljøvariabel (sat i pipeline)
        target_env = os.environ.get("TARGET_ENV", "dev")
        app.log.info(f"Opretter Azure engine for miljoe: {target_env}")

        # Hent Azure konfiguration for target miljø
        azure_config = get_config_for_project(f"azure-jn-{target_env}", "leverance")

        # Konfigurer Azure server og databaser og byg engine
        azure_server = azure_config.__class__.DB_SERVER
        app.log.info(f"Azure SQL Server: {azure_server}")
        azure_config._change_server(server=azure_server, driver=18)
        azure_config.set_up_application_databases()
        azure_uri = azure_config.LEVERANCE_BUSINESS_DATABASE_URI()
        app.log.info(f"Azure database URI: {azure_uri}")
        azure_engine = create_engine(azure_uri, echo=False, fast_executemany=True)

        # Brug access token til at authenticate mod Azure SQL med service principal
        app.log.info("Konfigurerer Azure SQL authentication med access token")
        use_access_token_for_azure_sql(
            azure_engine,
            tenant_id=os.environ["AZURE_TENANT_ID"],
            client_id=os.environ["AZURE_CLIENT_ID"],
            client_secret=os.environ["AZURE_CLIENT_SECRET"],
        )
        app.log.info("Azure engine oprettet succesfuldt")

        return azure_engine
    except Exception as e:
        app.log.error(f"Fejl ved oprettelse af Azure engine: {e!s}", exc_info=True)
        raise Exception(f"Fejl ved oprettelse af Azure engine: {e!s}") from e
