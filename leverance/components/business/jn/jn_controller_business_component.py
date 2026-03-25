import json
import time
from uuid import UUID

from leverance.core.runners.service_runner import ServiceRunner
from leverance.core.logger_adapter import ServiceLoggerAdapter
from leverance.components.business.jn.jn_storage_account_business_component import (
    JNStorageAccountBusinessComponent,
)


class JNControllerBusinessComponent(ServiceRunner):
    """
    Denne Leverancekomponent håndterer udtrækning og processering af den
    transskriberede samtale mellem kunderådgiver og borger.

    Når read_and_sort_messages kaldes, udtrækkes alle beskeder fra Blob for det
    pågældende call-id, og den transskriberede tekst sorteres efter tid for at sikre
    kronologi i samtalen.
    """

    def __init__(self, request_uid: UUID, config_name=None) -> None:

        # Initialisér UID og servicenavn
        self.service_name = "jn"
        self.request_uid = request_uid
        super().__init__(self.service_name, self.request_uid, config_name=config_name)

        # Offset
        self.offset = "earliest"

        # Logger
        self.service_logger = ServiceLoggerAdapter(self.app.log)

        # Initialisér Azure Queue Client max message size (max 32)
        self.max_msg = 32

        self.jn_storage_account = JNStorageAccountBusinessComponent(self.request_uid)

    def _extract_messages_blob(
        self,
        call_id: str,
    ) -> list[dict[str, str]]:
        """
        Udtrækker beskeder fra Blob for det pågældende call-id.
        """

        # Opret ContainerClient
        container_name = "transcriptions"
        container_client = JNStorageAccountBusinessComponent(
            self.request_uid
        ).create_container_client(container_name)

        if not container_client:
            return []

        messages = []

        # Udtræk beskeder for både agent og caller
        for speaker in ["agent", "caller"]:

            blob_name = f"transcriptions-{call_id}-{speaker}.jsonl"

            # Download og slet blob
            try:
                # Download blob
                blob_client = container_client.get_blob_client(blob_name)
                blob_data = blob_client.download_blob().readall()

                # Slet blob
                try:
                    blob_client.delete_blob()
                except Exception as e:
                    self.service_logger.service_warning(
                        self, f"Kunne ikke slette Blob {blob_name}: {e}"
                    )

            except Exception as e:
                self.service_logger.service_warning(
                    self, f"Kunne ikke downloade Blob {blob_name}: {e}"
                )
                continue

            # Tjek om blobben er tom
            if not blob_data:
                self.service_logger.service_warning(self, f"Blob {blob_name} er tom!")
                continue

            # Udtræk beskeder fra blob-data
            try:
                # Decode blob-data
                data = blob_data.decode("utf-8")
                # Parse hver linje som et JSON-objekt. Tomme linjer ignoreres
                messages.extend(
                    [json.loads(line) for line in data.split("\n") if line.strip()]
                )
            except UnicodeDecodeError as e:
                self.service_logger.service_exception(
                    self, f"Kunne ikke decode Blob-data for blob {blob_name}: {e}"
                )
            except json.JSONDecodeError as e:
                self.service_logger.service_exception(
                    self,
                    f"Blob-data er ikke i korrekt JSON-format for blob {blob_name}: {e}",
                )
            except Exception as e:
                self.service_logger.service_exception(
                    self,
                    f"Fejl i udtræk af beskeder fra Blob-data for blob {blob_name}: {e}",
                )

        # Luk ContainerClient
        container_client.close()

        return messages

    def read_and_sort_messages(
        self,
        call_id: str,
    ) -> tuple[str, str, str, list[dict]]:
        """
        Henter alt transskriberet tekst fra Blob for det pågældende call-id.
        Herefter sorteres den transskriberede tekst efter det tidspunkt, som hvert
        tekststykke er blevet indsat i Blob.

        Argumenter:
        - call_id (str): Unikt ID for samtalen.

        Returnerer:
        - agent_id (str): Initialer på kunderådgiver.
        - koe_id (str): ID på køen som opkaldet kom fra.
        - cpr (str): CPR-nummer på borgeren.
        - samtale (list[dict]): Liste af beskeder i kronologisk rækkefølge.
            Hver besked er en dict med nøglerne 'speaker' og 'sentence'.
        """

        # Initialisér variabler
        samtale = []
        unsorted_messages = []
        agent_id = None
        koe_id = None
        cpr = None

        # Udtræk beskeder fra Blob
        messages = self._extract_messages_blob(call_id)

        # Udtræk og sortér beskeder
        try:
            # Afslut hvis der ikke er nogen beskeder
            if len(messages) == 0:
                self.service_logger.service_warning(
                    self,
                    f"Ingen beskeder til transskriberinger for call-id {call_id}",
                )
                return agent_id, koe_id, cpr, samtale

            for message in messages:
                if "status" in message:

                    # Udtræk status for opkald
                    call_status = message["status"]

                    # Håndtér start af opkald
                    if call_status == "start":

                        # Udtræk relevante værdier
                        call_id = message["call_id"]
                        agent_id = message["agent_id"]
                        koe_id = message["koe_id"]
                        cpr = message["cpr"]

                # Håndtér alle beskeder mellem start og slut
                if "sentence" in message:

                    # Udtræk relevante værdier
                    sentence = message.get("sentence", None)
                    timestamp = message.get("timestamp", None)
                    speaker = message.get("speaker", None)

                    if not (sentence and timestamp):
                        # Beskeden indeholder ikke valid information
                        self.service_logger.service_warning(
                            self,
                            f"Beskeden mangler enten 'sentence' eller 'timestamp' for call-id {call_id}",
                        )
                        continue

                    # Tilføj til liste
                    unsorted_messages.append(
                        {
                            "sentence": sentence,
                            "timestamp": timestamp,
                            "speaker": speaker,
                        }
                    )

            # Sortér liste ud fra timestamp
            sorted_messages = sorted(
                unsorted_messages, key=lambda message: float(message["timestamp"])
            )

            # Samler de sorterede beskeder i en liste med format som forventet af modellen
            samtale = [
                {
                    "speaker": message["speaker"],
                    "sentence": message["sentence"],
                }
                for message in sorted_messages
            ]

            # Log en advarsel hvis der mangler beskeder for en af parterne
            for speaker in ["agent", "caller"]:
                if not any(msg["speaker"] == speaker for msg in samtale):
                    self.service_logger.service_warning(
                        self,
                        f"Ingen beskeder for speaker '{speaker}' i call-id {call_id}. "
                        f"Tjek lydindstillinger på kunderådgiver {agent_id}'s pc.",
                    )

            self.service_logger.service_info(
                self,
                f"Beskeder for call-id {call_id} blev udtrukket og sorteret",
            )

            return agent_id, koe_id, cpr, samtale

        except Exception as e:
            self.service_logger.service_warning(
                self,
                f"Fejl i udtræk og sortering af beskeder for call-id {call_id}: {e}",
            )

    def azure_notify_status(self, agent_id: str, call_id: str, status: str) -> None:
        """
        Opretter en Azure Queue klient og sender en besked til køen om status på det
        pågældende opkald.

        Argumenter:
            agent_id (str): Initialer på kunderådgiver
            call_id (str): Unikt ID for samtalen
            status (str): Status på samtalen som skal sendes til Azure Queue
        """

        # Opret Azure Queue client og send 'end-summary'
        try:
            queue_name = f"status-{agent_id}"
            # Opret Azure Queue klient med storage account name og storage account key
            queue_client = self.jn_storage_account.create_queue_client(queue_name)

            # Vi fjerner alle tidligere beskeder, så det kun er den nyeste
            queue_client.clear_messages()

            # Sender 'end-summary' besked til Azure Queue
            start_time = time.time()
            message_content = {
                "call_id": call_id,
                "status": status,
                "timestamp": time.time(),
            }

            queue_client.send_message(
                json.dumps(message_content), time_to_live=self.jn_storage_account.TTL
            )

            # Stop tidtagning
            end_time = time.time()

            # Log den tid det tog at sende 'end-summary' til Azure Queue
            self.service_logger.service_info(
                self,
                f"Azure sendt besked med end-summary tog {end_time - start_time:.2f} sekunder for call-id: {call_id} for KR {agent_id}",
            )

        except Exception as e:
            self.service_logger.service_warning(
                self,
                f"Kunne ikke sende end-summary til Azure Queue for call-id {call_id} for KR {agent_id}: {e}",
            )
