import re
from datetime import datetime, timedelta
from uuid import UUID

from azure.storage.blob import ContainerClient
from azure.storage.queue import QueueClient, QueueServiceClient

from leverance.core.common.azure_helper import (
    get_auth_based_on_env,
)
from leverance.core.logger_adapter import ServiceLoggerAdapter
from leverance.core.runners.service_runner import ServiceRunner


class JNStorageAccountBusinessComponent(ServiceRunner):
    """
    Denne Leverancekomponent håndterer generering af tokens til Azure Storage-konto
    for JN-komponenten.
    """

    def __init__(self, request_uid: UUID, config_name=None) -> None:
        """
        Initialiserer JNStorageAccountBusinessComponent med den angivne request UUID.

        Args:
            request_uid: UUID for den aktuelle request
        """
        # Initialisér UID, servicenavn og config_name
        self.service_name = "jn"
        self.request_uid = request_uid
        self.config_name = config_name
        super().__init__(self.service_name, self.request_uid, config_name=self.config_name)

        # Sæt TTL til 1 time
        self.TTL = 3600

        self.service_logger = ServiceLoggerAdapter(self.app.log)

    def get_token(self) -> str:
        """
        Opretter et token til Azure Storage-kontoen ved hjælp af de konfigurerede
        credentials.

        Returns:
            str: Token til Azure Storage-kontoen
        """
        try:
            # Hent credential til Azure
            authentication = get_auth_based_on_env(
                self.app,
                tenant_key_name="JN_AZURE_IDENTITY_TENANT_ID",
                client_key_name="JN_AZURE_IDENTITY_CLIENT_ID",
                secret_key_name="JN_AZURE_IDENTITY_CLIENT_SECRET",
            )

            # Hent token til Azure Storage-kontoen
            token = authentication.credential.get_token("https://storage.azure.com/.default")
            expiration = datetime.now() + timedelta(
                seconds=token.expires_on - datetime.now().timestamp()
            )

            return {
                "token": token.token,
                "expires_on": expiration,
            }

        except Exception as e:
            self.service_logger.service_warning(
                self, f"Fejl ved generering af storage account token: {e!s}"
            )
            raise

    def _format_name(self, name: str) -> str:
        """
        Formaterer et givet navn ved at erstatte ugyldige tegn med underscores,
        fjerne mellemrum i starten og slutningen, erstatte mellemrum med bindestreger
        og konvertere alt til små bogstaver. Gyldige tegn: a-z, 0-9, '-', '.', og '/'.
        """
        return re.sub(r"[^a-z0-9\-./]", "_", name.lower()).strip().replace(" ", "-")

    def create_queue_client(
        self,
        queue_name: str,
    ) -> QueueClient:
        """
        Opretter en Azure Queue klient og tilhørende kø, hvis den ikke findes.

        Argumenter:
            queue_name: Navn på køen i Azure Queue Storage.
            storage_account_name: Navn på storage account i Azure Queue Storage.

        Returnerer:
            QueueClient: Den oprettede Azure Queue klient.
        """
        queue_name_format = self._format_name(queue_name)

        account_url = f"https://{self.app.config.JN_AZURE_STORAGE_ACCOUNT}.queue.core.windows.net"
        authentication = get_auth_based_on_env(
            self.app,
            tenant_key_name="JN_AZURE_IDENTITY_TENANT_ID",
            client_key_name="JN_AZURE_IDENTITY_CLIENT_ID",
            secret_key_name="JN_AZURE_IDENTITY_CLIENT_SECRET",
        )

        try:
            queue_service_client = QueueServiceClient(
                account_url=account_url,
                credential=authentication.get_secret_credential(),
            )

            queue_client = queue_service_client.get_queue_client(queue_name_format)

            try:
                queue_client.get_queue_properties()
                self.service_logger.service_info(
                    self, f"Køen '{queue_name_format}' eksisterer i Azure Queue."
                )
            except Exception:
                queue_client.create_queue()
                self.service_logger.service_info(
                    self, f"Køen '{queue_name_format}' blev oprettet i Azure Queue."
                )

            return queue_client

        except Exception as e:
            self.service_logger.service_exception(
                self, f"Fejl ved oprettelse af QueueClient {queue_name_format}: {e}"
            )

    def create_container_client(
        self,
        container_name: str,
    ) -> ContainerClient:
        """
        Opretter en Azure Container klient, hvis den ikke findes.

        Argumenter:
            container_name: Navn på containeren i Azure Blob Storage.

        Returnerer:
            ContainerClient: Den oprettede Azure Container klient.
        """
        # Opret account_url
        account_url = f"https://{self.app.config.JN_AZURE_STORAGE_ACCOUNT}.blob.core.windows.net"
        authentication = get_auth_based_on_env(
            self.app,
            tenant_key_name="JN_AZURE_IDENTITY_TENANT_ID",
            client_key_name="JN_AZURE_IDENTITY_CLIENT_ID",
            secret_key_name="JN_AZURE_IDENTITY_CLIENT_SECRET",
        )

        try:
            # Opret ContainerClient
            container_client = ContainerClient(
                account_url=account_url,
                container_name=container_name,
                credential=authentication.get_secret_credential(),
            )
            return container_client

        except Exception as e:
            self.service_logger.service_exception(
                self,
                f"Fejl ved oprettelse af ContainerClient for container {container_name}: {e}",
            )
