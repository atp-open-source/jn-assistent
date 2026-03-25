import io, json, os, queue, threading, time, tempfile, requests
from typing import Any, Dict, Union, Optional
from uuid import uuid4
from datetime import datetime as dt, timedelta
from loguru import logger
from dotenv import load_dotenv
from azure.identity import ClientSecretCredential, DefaultAzureCredential
from azure.core.credentials import AccessToken, TokenCredential
from azure.storage.blob import BlobServiceClient
from azure.storage.queue import QueueServiceClient
from openai import AzureOpenAI, APIError
from pydub import AudioSegment

from audio_streamer.config import BaseConfig


class TokenCredentialAdapter(TokenCredential):
    """
    Adapter-klasse til at bruge token med Azure Storage SDK.
    """

    def __init__(self, token: str, expiration: str):
        self.token = token
        # Konvertér DD-MM-YYYY:HH:MM til datetime-objekt
        try:
            self.expires_on = dt.strptime(expiration, "%d-%m-%Y:%H:%M").timestamp()
        except ValueError:
            logger.warning(
                f"Could not parse expiration '{expiration}', using current time + 1 hour."
            )
            self.expires_on = (dt.now() + timedelta(hours=1)).timestamp()

    def get_token(self, *scopes, **kwargs) -> AccessToken:
        """
        Returnerer token i det format som Azure SDK forventer.
        """
        return AccessToken(token=self.token, expires_on=self.expires_on)


class AzureOpenAITranscriber:
    """
    Håndterer buffering af lyd, transskribering via Azure OpenAI, og gemmer resultatet til Azure Blob Storage.
    """

    def __init__(
        self,
        args: Dict[str, str],
        config: BaseConfig,
        speaker: str,
        controller_version: str = "onprem",
    ):
        """
        Initialiserer transcribereren.

        Args:
            args: Kommandolinje argumenter (CallID, AgentID, etc.).
            config: Konfigurationsobjekt.
            speaker: Taleren der skal behandles ('agent' eller 'caller').
            controller: Controller type ('azure' eller 'onprem').
        """
        self.args = args
        self.config = config
        self.call_id = args["CallID"]
        self.agent_id = args["AgentID"]
        self.speaker = speaker
        self.controller_version = controller_version
        self.transcription_results = []
        self.min_chunk_duration_seconds = 30
        self.transcription_container = "transcriptions"

        # Buffere og metadata lagring for en enkelt taler
        self.buffer = io.BytesIO()
        self.metadata = None
        self.last_transcription_time = time.time()

        # --- Azure OpenAI klient initialisering ---
        try:
            logger.info(
                f"Call_id {self.call_id}: Initializing Azure OpenAI client for {speaker}..."
            )

            # Hvis der køres i dev, brug DefaultAzureCredential
            if self.config.ENV == "dev":
                self.credentials = DefaultAzureCredential()
            else:
                self.credentials = ClientSecretCredential(
                    tenant_id=os.getenv("AZURE_TENANT_ID"),
                    client_id=os.getenv("AZURE_CLIENT_ID"),
                    client_secret=os.getenv("AZURE_CLIENT_SECRET"),
                )
            self._initialize_openai_client()
            self.client_ready = True
        except Exception as e:
            logger.exception(
                f"Call_id {self.call_id}: Failed to initialize Azure OpenAI client: {e}"
            )
            self.client_ready = False

    def _initialize_openai_client(self):
        """
        Initialiserer Azure OpenAI klienten.
        """

        token = self.credentials.get_token(
            "https://cognitiveservices.azure.com/.default"
        )
        self.expires_on = token.expires_on
        self.openai_client = AzureOpenAI(
            azure_deployment="gpt-4o-mini-transcribe",
            azure_endpoint=self.config.AZURE_OPENAI_ENDPOINT,
            api_version="2025-03-01-preview",
            api_key=token.token,
        )
        logger.info(
            f"Call_id: {self.call_id} Azure OpenAI client initialized successfully."
        )

    def _get_storage_token(self) -> Optional[TokenCredentialAdapter]:
        """
        Henter token til Azure Storage.
        """

        try:
            # Hent token fra sta_credentials endpoint baseret på controller type
            if not hasattr(self.config, "LEVERANCE_URL_STA_CREDENTIALS"):
                logger.error(
                    f"Call_id {self.call_id}: Configuration missing 'LEVERANCE_URL_STA_CREDENTIALS'. Cannot get storage token."
                )
                return None
            endpoint = self.config.LEVERANCE_URL_STA_CREDENTIALS

            response = requests.get(
                f"{endpoint}?uid={uuid4()}",
                verify=False,
            )
            response.raise_for_status()
            values = response.json()
            token, expires_on = values["token"], values["expires_on"]
            logger.info(
                f"Call_id {self.call_id}: Successfully retrieved Azure Storage token from {endpoint}."
            )
            return TokenCredentialAdapter(token, expires_on)
        except Exception as e:
            logger.exception(
                f"Call_id {self.call_id}: Error fetching token for Azure Storage: {e}"
            )
            return None

    def _create_blob_service_client(self) -> Optional[BlobServiceClient]:
        """
        Opretter en klient til Azure Blob Storage.
        """

        token_credential = self._get_storage_token()
        if not token_credential:
            logger.error(
                f"Call_id {self.call_id}: Failed to get storage token, cannot create BlobServiceClient."
            )
            return None

        if not hasattr(self.config, "BLOB_ACCOUNT_URL"):
            logger.error(
                f"Call_id {self.call_id}: Configuration missing 'BLOB_ACCOUNT_URL'. Cannot create BlobServiceClient."
            )
            return None

        try:
            blob_service_client = BlobServiceClient(
                account_url=self.config.BLOB_ACCOUNT_URL,
                credential=token_credential,
            )
            logger.info(
                f"Call_id {self.call_id}: BlobServiceClient created successfully."
            )
            return blob_service_client
        except Exception as e:
            logger.exception(
                f"Call_id {self.call_id}: Error creating BlobServiceClient: {e}"
            )
            return None

    def _create_queue_service_client(self) -> Optional[QueueServiceClient]:
        """
        Opretter en klient til Azure Queue Storage.
        """

        token_credential = self._get_storage_token()
        if not token_credential:
            logger.error(
                f"Call_id {self.call_id}: Failed to get storage token, cannot create QueueServiceClient."
            )
            return None

        if not hasattr(self.config, "QUEUE_ACCOUNT_URL"):
            logger.error(
                f"Call_id {self.call_id}: Configuration missing 'QUEUE_ACCOUNT_URL'. Cannot create QueueServiceClient."
            )
            return None

        try:
            queue_client = QueueServiceClient(
                account_url=self.config.QUEUE_ACCOUNT_URL,
                credential=token_credential,
            )
            logger.info(
                f"Call_id {self.call_id}: QueueServiceClient created successfully."
            )
            return queue_client
        except Exception as e:
            logger.exception(
                f"Call_id {self.call_id}: Error creating QueueServiceClient: {e}"
            )
            return None

    def _upload_to_queue(self, queue_name: str, data: str) -> bool:
        queue_client = self._create_queue_service_client()
        if not queue_client:
            return False

        try:
            queue_client.get_queue_client(queue_name).send_message(data)
            logger.info(
                f"Call_id {self.call_id}: Data uploaded to queue '{queue_name}'."
            )
            return True
        except Exception as e:
            logger.exception(
                f"Call_id {self.call_id}: Error uploading data to queue '{queue_name}': {e}"
            )
            return False

    def _upload_to_blob(self, blob_name: str, data: str) -> bool:
        """
        Uploader data (som JSONL string) til en append blob.
        """

        blob_service_client = self._create_blob_service_client()
        if not blob_service_client:
            return False

        try:
            append_blob_client = blob_service_client.get_blob_client(
                container=self.transcription_container, blob=blob_name
            )

            # Sikr at container eksisterer (valgfrit, afhænger af opsætning)
            try:
                container_client = blob_service_client.get_container_client(
                    self.transcription_container
                )
                if not container_client.exists():
                    container_client.create_container()
                    logger.info(
                        f"Call_id {self.call_id}: Container '{self.transcription_container}' created."
                    )
            except Exception as ce:
                logger.warning(
                    f"Call_id {self.call_id}: Could not ensure container '{self.transcription_container}' exists or create it: {ce}"
                )

            # Tjek om blob eksisterer, opret hvis ikke
            try:
                append_blob_client.get_blob_properties()
            except Exception:
                # ResourceNotFoundError forventet hvis blob ikke eksisterer
                logger.info(
                    f"Call_id {self.call_id}: Append blob '{blob_name}' not found, creating..."
                )
                append_blob_client.create_append_blob()
                logger.info(
                    f"Call_id {self.call_id}: Append blob '{blob_name}' created."
                )

            # Tilføj data
            data_bytes = data.encode("utf-8")
            append_blob_client.append_block(data_bytes)
            logger.info(
                f"Call_id {self.call_id}: Data appended to blob '{blob_name}' in container '{self.transcription_container}'."
            )
            return True

        except Exception as e:
            logger.exception(
                f"Call_id {self.call_id}: Error uploading data to blob '{blob_name}': {e}"
            )
            return False

    def _get_buffer_duration(self) -> float:
        """
        Beregner varigheden af lyd i bufferen i sekunder.
        """

        if not self.metadata or self.buffer.tell() == 0:
            return 0.0

        meta = self.metadata
        bytes_per_second = meta["frame_rate"] * meta["sample_width"] * meta["channels"]
        if bytes_per_second == 0:
            return 0.0
        return self.buffer.tell() / bytes_per_second

    def _transcribe_chunk(self):
        """
        Transskriberer lyddata som er i bufferen nu.
        """

        if not self.client_ready:
            logger.warning(
                f"Call_id {self.call_id}: OpenAI client not ready, skipping transcription."
            )
            # Ryd buffer for at forhindre overflow hvis klient aldrig bliver klar
            self.buffer = io.BytesIO()
            return

        # Tjek om token udløber inden for de næste 60 sekunder
        if self.expires_on - time.time() < 60:
            self._initialize_openai_client()

        buffer_size = self.buffer.tell()

        if buffer_size == 0 or not self.metadata:
            logger.debug(
                f"Call_id {self.call_id}: No data or metadata to transcribe for {self.speaker}."
            )
            return

        logger.info(
            f"Call_id {self.call_id}: Preparing {buffer_size} bytes for {self.speaker} for transcription..."
        )
        self.buffer.seek(0)
        audio_data = self.buffer.read()

        try:
            # Brug pydub til at indlæse rå lyd og eksportere som WAV til OpenAI
            audio_segment = AudioSegment.from_raw(
                io.BytesIO(audio_data),
                sample_width=self.metadata["sample_width"],
                frame_rate=self.metadata["frame_rate"],
                channels=self.metadata["channels"],
            )

            # Opret en midlertidig WAV fil
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
                tmp_wav_path = tmp_wav.name
                audio_segment.export(tmp_wav_path, format="wav")

            logger.info(
                f"Call_id {self.call_id}: Sending audio chunk for {self.speaker} to Azure OpenAI..."
            )
            # Send til OpenAI
            with open(tmp_wav_path, "rb") as audio_file:
                start_time = time.time()
                model_response = self.openai_client.audio.transcriptions.create(
                    model="gpt-4o-mini-transcribe",
                    file=audio_file,
                    response_format="json",
                    prompt=f"""
                    Du er en AI-assistent, der har til opgave at transskribere lyd.
                    Du vil få mindre lydfiler, der indeholder en samtale mellem to personer.
                    En kunderådgiver (Agent) eller en borger (Caller) der ringer ind.

                    I dette tilfælde er det {self.speaker} der taler.

                    Venligst transskriber alt, hvad der siges i samtalen!

                    Tilføj ikke mere information end det, der er i lydfilen.

                    Hvis der ikke siges noget, så skriv "Ingen tale".
                    Returner aldrig "Ingen tale" i transskriptionen, hvis der er tale i lydfilen.
                    """,
                )
                end_time = time.time()
                logger.info(
                    f"Call_id {self.call_id}: Transcription for speaker {self.speaker} received in {end_time - start_time:.2f}s."
                )
                self.transcription_results.append(
                    {
                        "speaker": self.speaker,
                        "timestamp": time.time(),
                        "text": model_response.text,
                    }
                )

        except APIError as e:
            logger.error(
                f"Call_id {self.call_id}: Azure OpenAI API error during transcription for speaker {self.speaker}: {e}, body: {e.body}, request: {e.request}"
            )
        except Exception as e:
            logger.exception(
                f"Call_id {self.call_id}: Error during transcription process for speaker {self.speaker}: {e}"
            )
        finally:
            # Ryd op i midlertidig fil
            if "tmp_wav_path" in locals() and os.path.exists(tmp_wav_path):
                try:
                    os.remove(tmp_wav_path)
                except Exception as e_rem:
                    logger.warning(
                        f"Call_id {self.call_id}: Could not remove temporary file {tmp_wav_path}: {e_rem}"
                    )
            # Nulstil bufferen for taleren
            self.buffer = io.BytesIO()
            self.last_transcription_time = time.time()

    def process_queue(self, data_queue: queue.Queue, stop_event: threading.Event):
        """
        Behandler data fra en enkelt kø (enten agent eller caller).

        Args:
            data_queue: Kø med lyddata
            stop_event: Event til at signalere hvornår behandling skal stoppe
        """
        data_upload = {
            "call_id": self.call_id,
            "status": "start-call",
            "timestamp": time.time(),
        }
        self._upload_to_queue(
            f"status-{self.agent_id.lower()}", json.dumps(data_upload)
        )
        logger.info(
            f"Call_id {self.call_id}: Starting OpenAI transcription processing loop for {self.speaker}."
        )
        while not stop_event.is_set() or not data_queue.empty():
            processed_data = False
            try:
                # Kort timeout for at forhindre blokering
                data = data_queue.get(timeout=0.1)
                processed_data = True

                # Metadata
                if isinstance(data, str):
                    meta_dict = json.loads(data)
                    if meta_dict.get("status") == "start":
                        logger.info(
                            f"Call_id {self.call_id}: Received start metadata for {self.speaker}: {meta_dict}"
                        )
                        self.metadata = meta_dict
                    elif meta_dict.get("status") == "end":
                        logger.info(
                            f"Call_id {self.call_id}: Received end metadata for {self.speaker}."
                        )
                        # Udløs eventuelt endelig transskription for denne taler hvis nødvendigt
                    continue

                if data and self.metadata:
                    self.buffer.write(data)
                    # Tjek om bufferens varighed overstiger tærskel
                    current_duration = self._get_buffer_duration()
                    if current_duration >= self.min_chunk_duration_seconds:
                        logger.info(
                            f"Call_id {self.call_id}: {self.speaker} buffer reached {current_duration:.2f}s, triggering transcription."
                        )
                        self._transcribe_chunk()

            except queue.Empty:
                # Køen er tom, vent blot kortvarigt
                pass
            except Exception as e:
                logger.exception(
                    f"Call_id {self.call_id}: Error processing queue for {self.speaker}: {e}"
                )

            # Hvis ingen data blev behandlet, sov kort for at forhindre busy-waiting
            if not processed_data:
                time.sleep(0.05)
        data_upload = {
            "call_id": self.call_id,
            "status": "end-call",
            "timestamp": time.time(),
        }
        self._upload_to_queue(
            f"status-{self.agent_id.lower()}", json.dumps(data_upload)
        )
        logger.info(
            f"Call_id {self.call_id}: Stop event set and queue empty for {self.speaker}, finalizing transcription."
        )
        self.finalize()

    def finalize(self):
        """
        Transskriberer eventuel resterende lyd og uploader den fulde transskription til Blob.
        """

        logger.info(
            f"Call_id {self.call_id}: Finalizing transcription for {self.speaker}..."
        )
        if not self.client_ready:
            logger.error(
                f"Call_id {self.call_id}: Cannot finalize transcription, OpenAI client not initialized."
            )
            return

        # Transskribér eventuelle resterende data i bufferen
        if self.buffer.tell() > 0:
            logger.info(
                f"Call_id {self.call_id}: Transcribing remaining data for {self.speaker}..."
            )
            self._transcribe_chunk()

        # --- Upload transskriptionsresultater til Azure Blob Storage som JSONL ---
        if self.transcription_results:
            # Definér blob navn - inkludér taleren i filnavnet
            blob_name = f"transcriptions-{self.call_id}-{self.speaker}.jsonl"
            logger.info(
                f"Call_id {self.call_id}: Preparing to upload transcription results to blob: {blob_name}"
            )

            # Formatér resultater som JSONL string
            jsonl_data = ""
            # Sortér resultater efter timestamp før oprettelse af JSONL
            sorted_results = sorted(
                self.transcription_results, key=lambda x: x.get("timestamp", 0)
            )
            line_data_start = {
                "status": "start",
                "call_id": self.call_id,
                "agent_id": self.agent_id,
                "koe_id": self.args.get("Queue", ""),
                "cpr": self.args.get("CPR", ""),
                "time": dt.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "sentence": "",
            }

            jsonl_data += json.dumps(line_data_start, ensure_ascii=False) + "\n"
            for result in sorted_results:
                # Tilføj call_id og agent_id til hver linje for konsistens med azure_store.py output
                line_data = {
                    "type": "transcript",
                    "call_id": self.call_id,
                    "agent_id": self.agent_id,
                    "speaker": result.get("speaker"),
                    "timestamp": result.get("timestamp"),
                    "time": dt.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                    "sentence": result.get("text"),
                    "queue_id": self.args.get("Queue", ""),
                    "cpr": self.args.get("CPR", ""),
                }
                try:
                    jsonl_data += json.dumps(line_data, ensure_ascii=False) + "\n"
                except Exception as json_e:
                    logger.error(
                        f"Call_id {self.call_id}: Error converting result to JSON: {result} - {json_e}"
                    )
                    # Spring denne linje over hvis den ikke kan serialiseres
                    continue

            line_data_end = {
                "status": "end",
                "call_id": self.call_id,
                "agent_id": self.agent_id,
                "koe_id": self.args.get("Queue", ""),
                "cpr": self.args.get("CPR", ""),
                "time": dt.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "sentence": "",
            }

            jsonl_data += json.dumps(line_data_end, ensure_ascii=False) + "\n"
            if jsonl_data:
                # Upload JSONL dataen
                upload_success = self._upload_to_blob(blob_name, jsonl_data)

                if upload_success:
                    logger.info(
                        f"Call_id {self.call_id}: Transcription for {self.speaker} successfully uploaded to blob: {blob_name}"
                    )
                else:
                    logger.error(
                        f"Call_id {self.call_id}: Failed to upload transcription for {self.speaker} to blob: {blob_name}"
                    )
            else:
                logger.warning(
                    f"Call_id {self.call_id}: No valid transcription data to upload for {self.speaker}."
                )
        else:
            logger.warning(
                f"Call_id {self.call_id}: No transcription results generated for {self.speaker}, skipping upload and notification."
            )

        logger.info(
            f"Call_id {self.call_id}: Finalization complete for {self.speaker}."
        )
