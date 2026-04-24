import json
import time
import uuid
from datetime import datetime as dt
from typing import Any

import requests
from azure.core.credentials import AccessToken, TokenCredential
from azure.storage.blob import BlobClient, BlobServiceClient
from azure.storage.queue import QueueClient, QueueServiceClient
from loguru import logger

from audio_streamer.config import DevConfig, ProdConfig


class TokenCredentialAdapter(TokenCredential):
    """
    Adapter-klasse til at bruge en rå token string med Azure Storage SDK.
    """

    def __init__(self, token: str, expiration: str):
        """
        Initialisér med den givne token string og udløb.

        Args:
            token: Autentificerings token
            expiration: Token udløbstidspunkt
        """
        self.token = token

        # Konvertér tid fra DD-MM-YYYY:HH:MM til datetime-objekt
        self.token_expiration = dt.strptime(expiration, "%d-%m-%Y:%H:%M")

    def get_token(self, *scopes, **kwargs) -> AccessToken:
        """
        Returnér token i det format som Azure SDK forventer.

        Returns:
            AccessToken: Token med udløbsinformation
        """
        return AccessToken(token=self.token, expires_on=self.token_expiration.timestamp())


class BaseAzureStorage:
    """
    Azure Blob og Queue Storage implementering.
    """

    def __init__(self, config: DevConfig | ProdConfig, agent_id: str, speaker: str):
        """
        Initialisér Azure storage.

        Args:
            config: Konfigurationsobjekt
            agent_id: Kunderådgivers initialer
            speaker: Hvem der taler ('agent' eller 'caller')
        """
        self.config = config
        self.agent_id = agent_id
        self.speaker = speaker
        self.audio_container_name = self._format_name("audio")
        self.status_audio = self._format_name("status-audio")
        self.status_queue = self._format_name(f"status-{self.agent_id}")

        self.storage_client, self.storage_expires = self._create_storage_client(
            container_name=self.audio_container_name
        )
        self.queue_client, self.queue_expire = self._create_queue_client(
            queue_name=self.status_audio
        )
        if self.speaker == "caller":
            self.queue_status_client, self.queue_status_expire = self._create_queue_client(
                queue_name=self.status_queue
            )
        else:
            self.queue_status_client, self.queue_status_expire = None, None

    def _create_client(
        self,
        is_queue: bool = True,
        queue_name: str | None = None,
        container_name: str | None = None,
    ) -> tuple[QueueClient, float] | tuple[BlobClient, float]:
        """
        Opret Azure klient (Queue eller Blob).
        """
        if not (queue_name or container_name):
            raise ValueError("queue_name or container_name must be provided")

        resource = "queue" if is_queue else "blob"
        account_url = f"https://{self.config.STORAGE_ACCOUNT_NAME}.{resource}.core.windows.net"
        api_url = self.config.LEVERANCE_URL + "/sta_credentials"

        try:
            response = requests.get(f"{api_url}?uid={uuid.uuid1()}", verify=False)
            response.raise_for_status()
            values = response.json()
            token, expires_on = values["token"], values["expires_on"]

            token_adapted = TokenCredentialAdapter(token, expires_on)

            if is_queue:
                client = QueueServiceClient(
                    account_url=account_url,
                    credential=token_adapted,
                )

                queue_client = client.get_queue_client(queue_name)
                try:
                    queue_client.get_queue_properties()
                    logger.info(f"Queue '{queue_name}' found.")
                except Exception:
                    queue_client.create_queue()
                    logger.info(f"Queue '{queue_name}' created.")

                return queue_client, token_adapted.token_expiration
            else:
                client = BlobServiceClient(
                    account_url=account_url,
                    credential=token_adapted,
                )

                container_client = client.get_container_client(container_name)
                if not container_client.exists():
                    container_client.create_container()
                    logger.info(f"Container '{container_name}' created.")

                return container_client, token_adapted.token_expiration

        except Exception as e:
            logger.exception(f"Error creating Azure client: {e}")
            raise

    def _create_storage_client(self, container_name: str) -> tuple[BlobServiceClient, float]:
        """
        Opret Azure Blob storage klient.
        """
        return self._create_client(is_queue=False, container_name=container_name)

    def _create_queue_client(self, queue_name: str) -> tuple[QueueServiceClient, float]:
        """
        Opret Azure Queue klient.
        """
        return self._create_client(is_queue=True, queue_name=queue_name)

    def get_audio_status_queue(self) -> QueueClient:
        """
        Hent Azure Queue klienten for køen 'status-audio'.
        """
        if dt.now() > self.queue_expire:
            self.queue_client, self.queue_expire = self._create_queue_client(
                queue_name=self.status_audio
            )
        return self.queue_client

    def get_status_queue(self) -> QueueClient:
        """
        Hent Azure status Queue klienten for køen 'status-{agent_id}'.
        """
        if self.queue_status_client and dt.now() > self.queue_status_expire:
            self.queue_status_client, self.queue_status_expire = self._create_queue_client(
                queue_name=self.status_queue
            )
        return self.queue_status_client

    def get_blob(self, blob_name: str) -> BlobClient:
        """
        Hent Azure Blob klienten.
        """
        if dt.now() > self.storage_expires:
            self.storage_client, self.storage_expires = self._create_storage_client(
                container_name=self.audio_container_name
            )
        return self.storage_client.get_blob_client(blob_name)

    def _format_name(self, name: str) -> str:
        """
        Formatér navn til Azure storage, for at undgå ugyldige tegn.
        """
        import re

        return re.sub(r"[^a-z0-9\-./]", "_", name.lower()).strip()


class AzureStorage:
    """
    Forenklet Azure Storage-håndtering af lyddata.
    """

    def __init__(
        self,
        config: DevConfig | ProdConfig,
        speaker: str,
        call_id: str,
        agent_id: str,
        queue_id: str,
        cpr: str = "",
    ):
        """
        Initialisér AzureStorage.

        Argumenter:
            config: Konfigurationsobjekt
            speaker: Højttaleridentifikation ('agent' eller 'caller')
            call_id: Opkalds-id
            agent_id: Agent-id
            queue_id: Kø-id
            cpr: CPR-nummer (valgfrit)
        """
        self.config = config
        self.speaker = speaker
        self.call_id = call_id
        self.agent_id = agent_id
        self.queue_id = queue_id
        self.cpr = cpr
        self.segment_count = 0
        self.azure_storage = BaseAzureStorage(config, agent_id=agent_id, speaker=speaker)
        self.status_audio = self.azure_storage.status_audio
        self.status_queue = self.azure_storage.status_queue

        # Send startbesked til 'status-{agent_id}' for caller
        start_besked_status_agent = self._status_besked(
            status="start-call", queue_name=self.status_queue
        )
        if speaker == "caller":
            self._send_status_message(start_besked_status_agent, self.status_queue)

        # Send startbesked til 'status-audio' (sker både for caller og agent)
        start_besked_status_audio = self._status_besked(
            status="start", queue_name=self.status_audio
        )
        self._send_status_message(start_besked_status_audio, self.status_audio)

    def _status_besked(self, status: str, queue_name: str) -> str:
        """
        Opret statusbesked afhængigt af hvilken queue, det skal sendes til.
        """
        if queue_name == self.status_audio:
            return {
                "call_id": self.call_id,
                "agent_id": self.agent_id,
                "koe_id": self.queue_id,
                "speaker": self.speaker,
                "cpr": self.cpr,
                "status": status,
                "total_segments": self.segment_count,
                "timestamp": time.time(),
            }
        elif queue_name == self.status_queue:
            return {
                "call_id": self.call_id,
                "status": status,
                "timestamp": time.time(),
            }

    def store_segment(self, data: bytes, metadata: dict[str, Any]) -> None:
        """
        Gem et segment af lyddata til Azure Blob Storage og send metadata til Queue.

        Argumenter:
            data: Lyddata som skal gemmes
            metadata: Metadata for lydsegmentet
        """
        if not data:
            return

        try:
            # Opret blob-navn med segmentnummer
            blob_name = f"{self.call_id}-{self.speaker}-segment{self.segment_count}"

            # Opret blob klient
            blob_client = self.azure_storage.get_blob(blob_name=blob_name)

            # Upload blob
            blob_client.upload_blob(data, overwrite=True)

            # Send notifikation til Queue
            self._send_segment_message(blob_name, len(data), metadata)

            # Forøg segment-tæller
            self.segment_count += 1

        except Exception as e:
            logger.exception(f"Call_id {self.call_id}: Error storing segment: {e}")

    def finalize(self) -> None:
        """
        Afslut optagelse.
        """

        # Send slutbesked til 'status-{agent_id}' for caller
        slut_besked_status_agent = self._status_besked(
            status="end-call", queue_name=self.status_queue
        )
        if self.speaker == "caller":
            self._send_status_message(slut_besked_status_agent, self.status_queue)

        # Send slutbesked til 'status-audio' (sker både for caller og agent)
        slut_besked_status_audio = self._status_besked(status="end", queue_name=self.status_audio)
        self._send_status_message(slut_besked_status_audio, self.status_audio)

    def _send_status_message(self, message: dict, queue_name: str) -> None:
        """
        Send statusbesked til queue.

        Argumenter:
            message: Dictionary med den besked der skal sendes.
            queue_name: Navn på queue som besked skal sendes til.
        """
        try:
            if queue_name == self.status_audio:
                # Hent klienten for køen 'status-audio'
                audio_queue_client = self.azure_storage.get_audio_status_queue()

                # Send besked til køen
                audio_queue_client.send_message(json.dumps(message))

            elif queue_name == self.status_queue:
                # Hent Queue-klient for køen 'status-{agent_id}'
                status_queue_client = self.azure_storage.get_status_queue()

                # Slet alle beskeder i køen
                status_queue_client.clear_messages()

                # Send besked til køen
                status_queue_client.send_message(json.dumps(message))

        except Exception as e:
            logger.exception(
                f"Call_id {self.call_id}: Der opstod en fejl med at sende status-besked til '{queue_name}': {e}"
            )

    def _send_segment_message(self, blob_name: str, size: int, metadata: dict[str, Any]) -> None:
        """
        Send notifikation om segment til køen.

        Argumenter:
            blob_name: Navn på blob
            size: Størrelse af segment i bytes
            metadata: Metadata for segmentet
        """
        try:
            logger.info(f"Call_id {self.call_id}: Metadata: {metadata}")

            # Opret besked med alle felter som AudioSegmentInfo i transcriber har brug for
            message = {
                "call_id": self.call_id,
                "agent_id": self.agent_id,
                "koe_id": self.queue_id,
                "speaker": self.speaker,
                "status": "segment",
                "segment_id": self.segment_count,
                "blob_name": blob_name,
                "size_bytes": size,
                "timestamp": time.time(),
                "cpr": self.cpr,
                "sample_width": metadata.get("sample_width", 2),
                "channels": metadata.get("channels", 1),
                "frame_rate": metadata.get("frame_rate", 44100),
            }

            # Send besked til køen 'status-audio'
            queue_client = self.azure_storage.get_audio_status_queue()
            queue_client.send_message(json.dumps(message))

        except Exception as e:
            logger.exception(f"Call_id {self.call_id}: Error sending segment notification: {e}")
