import time
import json
import logging
from uuid import uuid4
from email.utils import formatdate

from clients.base_client import BaseHelperClient, UserContext
from clients.audio_streamer_webservice_client import AudioStreamerWebserviceClient


class AzureStorageAccountClient(BaseHelperClient):
    """
    Klient som bruges af audiostreameren til at lave API-kald mod Azure Storage
    (Blob og Queue).

    Der laves direkte HTTP-kald i stedet for at bruge Azure SDK'en, for bedre at
    kunne logge kaldene i Locust.
    """

    def __init__(
        self,
        user_context: UserContext,
        storage_api_version: str = "2025-07-05",
    ):
        super().__init__(user_context)
        self.storage_api_version = storage_api_version
        self.transcriptions_container = "transcriptions"

    def _get_headers(self, token: str) -> dict:
        """Byg headers til Azure Storage REST API kald."""

        return {
            "Authorization": f"Bearer {token}",
            "x-ms-version": self.storage_api_version,
            "x-ms-date": formatdate(timeval=None, usegmt=True),
            "x-ms-client-request-id": str(uuid4()),
            "User-Agent": "locust-load-test/1.0 Python/3.x",
        }

    def upload_to_queue(
        self,
        queue_name: str,
        data: str,
        token: str | None = None,
    ) -> bool:
        """Upload en besked til en Azure Queue Storage kø via REST API."""

        headers = self._get_headers(token)
        xml_body = (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f"<QueueMessage><MessageText>{data}</MessageText></QueueMessage>"
        )
        url = f"{self.config.QUEUE_ACCOUNT_URL.rstrip('/')}/{queue_name}/messages"
        headers["Content-Type"] = "application/xml"

        resp, _ = self._call_endpoint(
            url,
            name="queue_send_message",
            method="POST",
            accepted_status_codes=[201],
            data=xml_body,
            headers=headers,
        )
        if resp is None:
            return False
        return True

    def send_status_to_queue(
        self,
        status: str,
        webservice_client: AudioStreamerWebserviceClient,
    ) -> bool:
        """Hent et nyt token via webservice_client og send status til køen."""

        token, _ = webservice_client.get_storage_token()
        if token is None:
            logging.error("Kunne ikke hente storage token for send_status_to_queue")
            return False

        data = {
            "call_id": self.call_id,
            "status": status,
            "timestamp": time.time(),
        }

        return self.upload_to_queue(
            f"status-{self.agent_id.lower()}",
            json.dumps(data),
            token=token,
        )

    def _ensure_container(self, container: str, headers: dict) -> bool:
        """Tjek om en blob container findes. Hvis ikke, log en fejl."""

        # Udfør en GET eksistens-tjek (SDK-mønster) og opret IKKE containeren, selvom den mangler.
        base = self.config.BLOB_ACCOUNT_URL.rstrip("/")
        get_url = f"{base}/{container}?restype=container"

        # Ny request id & UA pr. kald for at efterligne SDK pipeline adfærd
        exist_headers = dict(headers)
        exist_headers["x-ms-client-request-id"] = str(uuid4())

        resp, _ = self._call_endpoint(
            get_url,
            name="blob_container_get",
            method="GET",
            headers=exist_headers,
            accepted_status_codes=[200],
        )

        if resp is None:
            return False
        return True

    def _ensure_append_blob(self, container: str, blob: str, headers: dict) -> bool:
        """Tjek om en append blob findes. Hvis ikke, opret den."""

        base = self.config.BLOB_ACCOUNT_URL.rstrip("/")
        blob_url = f"{base}/{container}/{blob}"

        # Tjek om blobben findes via HEAD request
        resp, status_code = self._call_endpoint(
            blob_url,
            name="blob_head",
            method="HEAD",
            headers=headers,
            accepted_status_codes=[200, 404],
        )

        if resp is None:
            return False

        # Forventet manglende blob - opret den
        if status_code == 404:
            create_headers = {
                **headers,
                "x-ms-blob-type": "AppendBlob",
                "Content-Length": "0",
            }
            create_headers["x-ms-client-request-id"] = str(uuid4())
            create_resp, _ = self._call_endpoint(
                blob_url,
                name="blob_create",
                method="PUT",
                headers=create_headers,
                accepted_status_codes=[201, 409],
                data=b"",
            )
            if create_resp is None:
                return False

        return True

    def _append_block(
        self, container: str, blob: str, data_bytes: bytes, headers: dict
    ) -> bool:
        """Append en blok til en Azure Append Blob via REST API."""

        base = self.config.BLOB_ACCOUNT_URL.rstrip("/")
        url = f"{base}/{container}/{blob}?comp=appendblock"
        append_headers = {**headers, "Content-Length": str(len(data_bytes))}
        append_headers["x-ms-client-request-id"] = str(uuid4())

        resp, _ = self._call_endpoint(
            url,
            name="blob_append",
            method="PUT",
            headers=append_headers,
            data=data_bytes,
            accepted_status_codes=[201, 202],
        )
        if resp is None:
            return False
        return True

    def upload_to_blob(
        self,
        blob_name: str,
        data: str,
        webservice_client: AudioStreamerWebserviceClient,
    ) -> bool:
        """Kører hele flowet der er nødvendigt for at uploade data til en append blob."""

        token, _ = webservice_client.get_storage_token()
        if token is None:
            logging.error("Kunne ikke hente storage token for upload_to_blob")
            return False

        headers = self._get_headers(token)
        container = getattr(self, "transcriptions_container", "transcriptions")
        if not self._ensure_container(container, headers):
            return False
        if not self._ensure_append_blob(container, blob_name, headers):
            return False
        data_bytes = data.encode("utf-8")
        return self._append_block(container, blob_name, data_bytes, headers)
