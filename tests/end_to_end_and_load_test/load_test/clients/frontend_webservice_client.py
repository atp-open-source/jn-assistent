from clients.base_client import BaseHelperClient, UserContext


class FrontendWebserviceClient(BaseHelperClient):
    """
    Klient som bruges af frontenden til at lave API-kald mod webservice
    (on-prem app server eller Azure Web App).
    """

    def __init__(self, user_context: UserContext):
        super().__init__(user_context)

    def fetch_status(self, last_seen_msg: str = "") -> str | None:
        """Hent status fra /fetch_status endpoint."""

        resp, _ = self._call_endpoint(
            self.config.LEVERANCE_URL + "/fetch_status",
            method="GET",
            params={
                "kr_initialer": self.agent_id,
                "last_seen_msg": last_seen_msg,
            },
            parse_json=True,
            json_response_fields=["Status"],
            inject_uid=True,
            verify=False,
        )

        if resp is not None:
            return resp["Status"]
        return None

    def get_notat(self) -> tuple[str | None, str | None]:
        """Hent notat fra /get_notat endpoint."""

        resp, _ = self._call_endpoint(
            self.config.LEVERANCE_URL + "/get_notat",
            method="GET",
            params={"kr_initialer": self.agent_id or ""},
            parse_json=True,
            json_response_fields=["notat", "call_id"],
            inject_uid=True,
            verify=False,
        )

        if resp is not None:
            return resp["notat"], resp["call_id"]
        return None, None

    def feedback(
        self,
        call_id: str,
        agent_id: str,
        feedback: str | None,
        rating: int | None,
        benyttet: bool | None,
    ) -> bool:
        """Send feedback til /feedback endpoint."""

        json_data = {
            "call_id": call_id,
            "agent_id": agent_id,
            "feedback": feedback or "",
            "rating": rating or -1,
            "benyttet": int(benyttet) if benyttet is not None else 1,
        }

        resp, _ = self._call_endpoint(
            self.config.LEVERANCE_URL + "/feedback",
            method="POST",
            inject_uid=True,
            verify=False,
            json=json_data,
        )

        return resp is not None
