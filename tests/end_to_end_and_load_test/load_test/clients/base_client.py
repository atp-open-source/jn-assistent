import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal
from uuid import uuid4

from locust.clients import HttpSession as LocustHttpSession

from audio_streamer.config import BaseConfig


@dataclass
class UserContext:
    """
    Kontekst for en Locust-bruger, der indeholder delt HTTP-klient, konfiguration,
    timestamp for load-testen og andet relevant metadata.
    """

    client: LocustHttpSession
    config: BaseConfig
    timestamp: str
    call_id: str | None = None
    agent_id: str | None = None
    koe_id: str | None = None
    cpr: str | None = None


class BaseHelperClient:
    """
    Baseklasse til oprettelse af hjælpeklienter til at kalde forskellige API'er med en
    delt Locust HTTP-klient og bruger-kontekst.
    """

    def __init__(
        self,
        user_context: UserContext,
    ):
        self.client = user_context.client
        self.config = user_context.config
        self.timestamp = user_context.timestamp
        self.call_id = user_context.call_id
        self.agent_id = user_context.agent_id
        self.koe_id = user_context.koe_id
        self.cpr = user_context.cpr

    def _generate_uid(self) -> str:
        """Generer et unikt UID for API kald."""
        return f"loadtest_{self.timestamp}_{uuid4()}"

    def _call_endpoint(
        self,
        endpoint: str,
        name: str | None = None,
        method: Literal["GET", "POST", "PUT", "HEAD"] = "GET",
        parse_json: bool = False,
        json_response_fields: Iterable[str] | None = None,
        accepted_status_codes: Iterable[int] | None = None,
        inject_uid: bool = False,
        **request_kwargs: Any,
    ) -> tuple[Any | None, int | None]:
        """
        Wrapper til at kalde et generisk endpoint med Locust-klienten
        og verificere respons.

        ### Argumenter:
        - `endpoint` (str): Endpoint-URL. Kan være relativ eller absolut.
        - `name` (str | None): Navn som kaldet skal logges som i Locust.
            Hvis ikke angivet, defaultes til `endpoint`.
        - `method` (Literal["GET", "POST", "PUT", "HEAD"]): HTTP-metode til kaldet.
        - `parse_json` (bool): Hvis True, parse responsen som JSON.
        - `json_response_fields` (Iterable[str] | None): Hvis parse_json er True,
            verificer at disse felter findes i JSON-responsen.
        - `accepted_status_codes` (Iterable[int] | None): Liste af
            acceptable HTTP statuskoder. Hvis ikke angivet, accepteres
            alle 2xx og 3xx koder.
        - `inject_uid` (bool): Hvis True, tilføjes et unikt 'uid' parameter
            til kaldet hvis det ikke allerede er til stede.
        - `**request_kwargs`: Yderligere keyword-argumenter til
            klientens get/post metoder, fx `params`, `data`, `json`, `headers`,
            `verify`, osv.

        ### Returnerer:
        - `data` (Any | None): Parsed JSON-respons eller rå tekstrespons hvis
            `json_response_fields` ikke er angivet. Returneres som None ved fejl.
        - `status_code` (int | None): HTTP statuskode fra responsen, eller None hvis
            der ikke modtages nogen respons.
        """

        # Tilføj unikt UID til kaldet hvis ikke allerede angivet
        if inject_uid:
            params = request_kwargs.get("params", {})
            data = request_kwargs.get("data", {})
            json_data = request_kwargs.get("json", {})

            uid_present = ("uid" in params) or ("uid" in data) or ("uid" in json_data)

            if not uid_present:
                uid = self._generate_uid()
                if method in ["GET", "HEAD"]:
                    params["uid"] = uid
                    request_kwargs["params"] = params
                elif json_data:
                    json_data["uid"] = uid
                    request_kwargs["json"] = json_data
                else:
                    data["uid"] = uid
                    request_kwargs["data"] = data

        # Vælg HTTP-metode
        match method:
            case "GET":
                method_func = self.client.get
            case "POST":
                method_func = self.client.post
            case "PUT":
                method_func = self.client.put
            case "HEAD":
                method_func = self.client.head
            case _:
                logging.error(f"Ugyldig HTTP-metode: {method}")
                return None, None

        # Udfør kaldet med Locust HTTP-klienten
        with method_func(
            url=endpoint,
            name=name or endpoint,
            catch_response=True,
            **request_kwargs,
        ) as resp:
            # Verificer at der er modtaget en respons
            if resp is None:
                logging.error(f"{endpoint} returnerede ingen response")
                return None, None

            # Verificer statuskode
            accepted = (
                resp.status_code in accepted_status_codes
                if accepted_status_codes
                else resp.status_code >= 200 and resp.status_code < 400
            )
            if not accepted:
                resp_text = getattr(resp, "text", "<no response text>") or "<empty response text>"
                resp.failure(f"Uacceptabel statuskode {resp.status_code}")
                logging.error(f"{endpoint} fejlede med statuskode {resp.status_code}: {resp_text}")
                return None, resp.status_code

            # Parse JSON-respons
            if parse_json:
                try:
                    data = resp.json()
                except Exception as e:
                    logging.error(f"Parse-fejl i {endpoint}: {e}")
                    resp.failure(f"Parse-fejl i {endpoint}: {e}")
                    return None, resp.status_code

                # Verificer at alle forventede felter er til stede
                if json_response_fields:
                    for field in json_response_fields:
                        if field not in data:
                            logging.error(f"Felt '{field}' mangler i {endpoint} response")
                            resp.failure(f"Felt '{field}' mangler i {endpoint} response")
                            return None, resp.status_code
            # Rå tekst-respons
            else:
                data = resp.text

            resp.success()

            return data, resp.status_code
