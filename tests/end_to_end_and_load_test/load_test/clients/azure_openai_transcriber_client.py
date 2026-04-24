# Vores load-test bruger CoRaL-datasættet som testdata
# @dataset{coral2024,
#   author    = {Dan Saattrup Nielsen, Sif Bernstorff Lehmann, Simon Leminen Madsen, Anders Jess Pedersen, Anna Katrine van Zee and Torben Blach},
#   title     = {CoRal: A Diverse Danish ASR Dataset Covering Dialects, Accents, Genders, and Age Groups},
#   year      = {2024},
#   url       = {https://hf.co/datasets/alexandrainst/coral},
# }

import logging
import os
import time
from typing import Literal
from uuid import uuid4

from azure.core.credentials import AccessToken
from azure.identity import (
    AzurePipelinesCredential,
    ClientSecretCredential,
    DefaultAzureCredential,
)
from clients.base_client import BaseHelperClient, UserContext


class AzureOpenAITranscriberClient(BaseHelperClient):
    """
    Klient som bruges af audiostreameren til at lave API-kald mod Azure OpenAI
    transskriberings-endpointet.

    Der laves direkte HTTP-kald i stedet for at bruge OpenAI SDK'en, for bedre at
    kunne logge kaldene i Locust.
    """

    def __init__(
        self,
        user_context: UserContext,
        openai_api_version: str = "2025-03-01-preview",
        deployment: str = "gpt-4o-mini-transcribe",
        speaker: Literal["agent", "caller"] = "agent",
        mock_transcription: bool = True,
    ):
        super().__init__(user_context)
        self.openai_api_version = openai_api_version
        self.deployment = deployment
        self.speaker = speaker
        self.mock_transcription = mock_transcription

        self.credential = self._get_credential()
        self.token = self._get_token()

    @staticmethod
    def _get_credential() -> (
        AzurePipelinesCredential | ClientSecretCredential | DefaultAzureCredential
    ):
        """
        Opret Azure Credential baseret på miljøet.

        Hvis miljøvariablene AZURE_TENANT_ID, AZURE_CLIENT_ID,
        AZURE_SERVICE_CONNECTION_ID og SYSTEM_ACCESSTOKEN er sat, bruges
        AzurePipelinesCredential (disse sættes i pipelinen). Denne credential bruger
        en service connection i Azure DevOps til at hente token.

        Hvis miljøvariablene AZURE_TENANT_ID, AZURE_CLIENT_ID og
        AZURE_CLIENT_SECRET er sat, bruges ClientSecretCredential.

        Ellers defaultes til DefaultAzureCredential.

        OBS: Hvis DefaultAzureCredential falder tilbage til AzureCliCredential, kan det
        give fejl hvis metoden kaldes mange gange samtidigt fra flere greenlets,
        da hvert kald skal invokere Azure CLI'en for at hente et token, hvilket skaber
        overhead og potentielle låseproblemer. Derfor anbefales det at bruge en af de
        andre metoder hvis muligt.
        """

        tenant_id = os.getenv("AZURE_TENANT_ID")
        client_id = os.getenv("AZURE_CLIENT_ID")

        if (
            tenant_id
            and client_id
            and (service_connection_id := os.getenv("AZURE_SERVICE_CONNECTION_ID"))
            and (system_access_token := os.getenv("SYSTEM_ACCESSTOKEN"))
        ):
            return AzurePipelinesCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                service_connection_id=service_connection_id,
                system_access_token=system_access_token,
            )
        elif tenant_id and client_id and (client_secret := os.getenv("AZURE_CLIENT_SECRET")):
            return ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
            )
        else:
            return DefaultAzureCredential()

    def _get_token(self) -> AccessToken:
        """Hent et gyldigt Azure OpenAI token og registrer kaldet i Locust."""

        response_length = 0
        exception = None
        start_time = time.perf_counter()

        # Forsøg at hente token
        try:
            token = self.credential.get_token("https://cognitiveservices.azure.com/.default")
            if (
                not token
                or not getattr(token, "token", None)
                or not getattr(token, "expires_on", None)
            ):
                raise Exception("Hentet token er None eller ugyldig")
            response_length = len(token.token)
        except Exception as e:
            logging.error(f"Fejl ved hentning af Azure OpenAI token: {e}")
            exception = e
            token = None
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        # Registrer kaldet i Locust
        self.client.request_event.fire(
            request_type="GET",
            name="azure_openai_token",
            response_time=elapsed_ms,
            response_length=response_length,
            exception=exception,
        )

        return token

    @staticmethod
    def _build_multipart(
        fields: list[tuple[str, str]], files: list[tuple[str, str, bytes, str]]
    ) -> tuple[bytes, str]:
        """Byg en multipart/form-data body."""

        boundary = f"----locust-{uuid4().hex}"
        crlf = "\r\n"
        parts = []
        for name, value in fields:
            parts.append(f"--{boundary}{crlf}")
            parts.append(f'Content-Disposition: form-data; name="{name}"{crlf}{crlf}')
            parts.append(f"{value}{crlf}")
        for field_name, filename, content, content_type in files:
            parts.append(f"--{boundary}{crlf}")
            parts.append(
                f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"{crlf}'
            )
            parts.append(f"Content-Type: {content_type}{crlf}{crlf}")
            parts.append(content)
            if not content.endswith(b"\r\n"):
                parts.append(crlf)
        parts.append(f"--{boundary}--{crlf}")
        body = b"".join(p if isinstance(p, bytes) else p.encode("utf-8") for p in parts)
        return body, f"multipart/form-data; boundary={boundary}"

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "coral_audio_30.wav",
    ) -> dict | None:
        """
        Send lyd til Azure OpenAI transskriberings-endpointet og returner
        transskriberingen, eller returner en mock-transskription.
        """

        if not self.token or self.token.expires_on - time.time() < 60:
            self.token = self._get_token()

        # Returner mock-transskription hvis angivet
        if self.mock_transcription:
            return {
                "speaker": self.speaker,
                "timestamp": time.time(),
                "text": "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
            }

        # Byg prompt
        prompt = f"""
                    Du er en AI-assistent, der har til opgave at transskribere lyd.
                    Du vil få mindre lydfiler, der indeholder en samtale mellem to personer.
                    En kunderådgiver (Agent) eller en borger (Caller) der ringer ind.

                    I dette tilfælde er det {self.speaker} der taler.

                    Venligst transskriber alt, hvad der siges i samtalen!

                    Tilføj ikke mere information end det, der er i lydfilen.

                    Hvis der ikke siges noget, så skriv "Ingen tale".
                    Returner aldrig "Ingen tale" i transskriptionen, hvis der er tale i lydfilen.
                    """

        # Forbered multipart body
        fields = [
            ("model", self.deployment),
            ("response_format", "json"),
            ("prompt", prompt),
        ]
        ctype = "audio/wav"
        files = [("file", filename or "coral_audio_30.wav", audio_bytes, ctype)]

        body, content_type = self._build_multipart(fields, files)

        # Byg URL og headers
        url = (
            f"{self.config.AZURE_OPENAI_ENDPOINT.rstrip('/')}/"
            f"openai/deployments/{self.deployment}/audio/transcriptions"
            f"?api-version={self.openai_api_version}"
        )
        headers = {
            "Authorization": f"Bearer {self.token.token}",
            "Accept": "application/json",
            "Content-Type": content_type,
        }

        # Lav POST request til transskriberings-endpointet
        resp, _ = self._call_endpoint(
            endpoint=url,
            name="openai_transcribe",
            method="POST",
            parse_json=True,
            json_response_fields=["text"],
            accepted_status_codes=[200],
            data=body,
            headers=headers,
        )

        result = {
            "speaker": self.speaker,
            "timestamp": time.time(),
            "text": resp["text"],
        }

        return result
