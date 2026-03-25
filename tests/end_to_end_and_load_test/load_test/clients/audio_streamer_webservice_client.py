from clients.base_client import BaseHelperClient


class AudioStreamerWebserviceClient(BaseHelperClient):
    """
    Klient som bruges af audiostreameren til at lave API-kald mod webservice
    (on-prem app server eller Azure Web App).
    """

    def get_config(self) -> str | None:
        """Hent kunderådgiver konfiguration via /get_config endpoint."""

        resp, _ = self._call_endpoint(
            self.config.LEVERANCE_URL_GET_CONFIG,
            method="GET",
            parse_json=True,
            json_response_fields=["miljoe"],
            inject_uid=True,
            params={"kr_initialer": self.agent_id or ""},
            verify=False,
        )

        if resp is not None:
            return resp["miljoe"]
        return None

    def get_storage_token(self) -> tuple[str | None, str | None]:
        """Hent et token til Azure Storage via /sta_credentials endpoint."""

        resp, _ = self._call_endpoint(
            self.config.LEVERANCE_URL_STA_CREDENTIALS,
            method="GET",
            parse_json=True,
            json_response_fields=["token", "expires_on"],
            inject_uid=True,
            params={
                "call_id": self.call_id or "",
                "storage_type": "azure",
            },
            verify=False,
        )

        if resp is not None:
            return resp["token"], resp["expires_on"]
        return None, None

    def process_call(self) -> bool:
        """Påbegynd generering af notat via /process_call endpoint."""

        resp, _ = self._call_endpoint(
            self.config.LEVERANCE_URL_PROCESS_CALL,
            method="GET",
            parse_json=True,
            json_response_fields=["msg"],
            inject_uid=True,
            params={
                "call_id": self.call_id or "",
                "storage_type": "azure",
            },
            verify=False,
        )

        if resp is not None:
            return True
        return False

    def health_check(self) -> bool:
        """Kald health-check endpointet /health_check."""

        url = self.client.base_url.rstrip("/").rstrip("/jn") + "/health-check"
        resp, _ = self._call_endpoint(
            url,
            name="/health-check",
            method="GET",
            parse_json=True,
            inject_uid=True,
            verify=False,
        )

        if resp is not None:
            return True
        return False
