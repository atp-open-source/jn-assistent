# Vores load-test bruger CoRaL-datasættet som testdata
# @dataset{coral2024,
#   author    = {Dan Saattrup Nielsen, Sif Bernstorff Lehmann, Simon Leminen Madsen, Anders Jess Pedersen, Anna Katrine van Zee and Torben Blach},
#   title     = {CoRal: A Diverse Danish ASR Dataset Covering Dialects, Accents, Genders, and Age Groups},
#   year      = {2024},
#   url       = {https://hf.co/datasets/alexandrainst/coral},
# }

import os
from pathlib import Path
import time
import json
import logging
import datetime as dt
from uuid import uuid4
import random

import gevent
from gevent.event import Event
from gevent.queue import Queue
from gevent.pool import Pool
from locust import HttpUser, task, between

from audio_streamer.config import BaseConfig

from clients.audio_streamer_webservice_client import AudioStreamerWebserviceClient
from clients.frontend_webservice_client import FrontendWebserviceClient
from clients.azure_storage_account_client import AzureStorageAccountClient
from clients.azure_openai_transcriber_client import AzureOpenAITranscriberClient
from clients.base_client import UserContext

from parameters import (
    TIMESTAMP,
    NUM_WORKERS,
    MIN_WAIT_TIME,
    MAX_WAIT_TIME,
    CALL_DURATION_RANGES,
    CALL_DURATION_WEIGHTS,
    MOCK_TRANSCRIPTION,
    MOCK_PROCESS_CALL,
)


class BaseJNHttpUser(HttpUser):
    """
    Locust HttpUser der simulerer en kunderådgiver der tager opkald og har
    audiostreameren kørende. For hvert opkald simuleres at audiostreameren:
    - Henter kunderådgiverens config (/get_config)
    - Henter et token til storage account (/sta_credentials)
    - Sender start-call status til status-køen
    - Løbende transskriberer lyddata fra både agent og caller
    - Sender end-call status til status-køen
    - Uploader transskriberinger til blob storage
    - Starter notatgenerering (/process_call)

    Derudover simuleres også at kunderådgiveren har frontenden åben, som:
    - Løbende henter statusopdateringer (/fetch_status)
    - Henter det genererede notat (/get_notat)
    - Sender feedback på notatet (/feedback)

    Tiden fra opkaldets afslutning til notatet er hentet logges i Locust som en
    separat request-type "total_response_time".

    Load testen kan startes med `pdm run locust -f <sti_til_denne_fil>`, hvorved der
    startes en lokal webserver op på http://localhost:8089, hvorfra testen kan
    konfigureres og startes.
    Alternativt kan testen køres i "headless" mode med flaget `--headless` samt andre
    relevante flag, herunder `-u` for antal brugere og `-r` for spawn rate.
    Se evt. hvordan testen køres i pipelinen i `ci/load_test.yml`, eller se
    Locust dokumentationen: https://docs.locust.io/en/stable/index.html
    """

    # Bruges af Locust til at identificere at dette er en baseklasse og derfor ikke
    # skal instantieres som en bruger
    abstract = True

    # Audiostreamer konfiguration. Skal sættes af subklasser
    config: BaseConfig | None = None

    # Host URL for leverance-endpoints. Skal sættes af subklasser
    host: str | None = None

    # Ventetid mellem opkald i sekunder
    wait_time = between(MIN_WAIT_TIME, MAX_WAIT_TIME)

    # Antal brugere der er startet op for denne worker
    user_count = 0

    worker_index: int | None = None

    # Indlæs lydfil til transskribering
    audio_path = Path("audio/coral_audio_30.wav")
    with audio_path.open("rb") as f:
        audio_bytes = f.read()

    def on_start(self):
        """
        Kaldes af Locust når en bruger startes op.

        Sætter unikt agent_id for brugeren, initialiserer variable og starter
        greenlet der simulerer frontend-kald.
        """

        # Lav bruger-id med stride NUM_WORKERS og offset worker_index,
        # således at brugere er unikke på tværs af workers
        if self.__class__.worker_index is None:
            self.__class__.worker_index = self.environment.runner.worker_index
        user_id = self.__class__.user_count * NUM_WORKERS + self.__class__.worker_index
        self.agent_id = f"L{user_id:03d}"
        self.__class__.user_count += 1

        self.call_id: str | None = None
        self.koe_id = "loadtest_queue"
        self.cpr = "1111111111"

        self.timestamp = TIMESTAMP

        self.end_call_time: float | None = None

        self.stopped = False

        # Pool til håndtering af greenlets for audiostreameren.
        # Maksimalt 3 greenlets: enqueue_data + 2x process_queue
        self.audio_streamer_pool = Pool(3)

        # Event der sættes når frontenden har hentet notatet
        self.fetched_notat_event = Event()

        # Start greenlet der simulerer frontend-kald
        self.fe_greenlet = gevent.spawn(self.simulate_fe)

    def on_stop(self):
        """
        Kaldes af Locust når en bruger stoppes.
        """

        self.stopped = True

        # Dræb igangværende greenlets
        self.audio_streamer_pool.kill()
        self.fe_greenlet.kill()

    @task
    def simulate_call(self):
        """
        Task der simulerer audiostreameren gennem et helt opkald.
        """

        # Lav et unikt call_id
        self.call_id = f"loadtest_{TIMESTAMP}-{str(uuid4())}-{self.agent_id}"

        # Registrer opkaldet
        if hasattr(self.environment, "active_calls") and isinstance(
            self.environment.active_calls, set
        ):
            self.environment.active_calls.add(self.call_id)

        # Nulstil event for hentning af notat
        self.fetched_notat_event.clear()

        # Opret webservice client
        audio_streamer_webservice_client = AudioStreamerWebserviceClient(
            self._get_user_context()
        )

        # Hent kunderådgiverens config
        kr_config = audio_streamer_webservice_client.get_config()
        if kr_config is None:
            logging.error(f"Kunne ikke hente config for agent_id: {self.agent_id}")
            if hasattr(self.environment, "active_calls") and isinstance(
                self.environment.active_calls, set
            ):
                self.environment.active_calls.discard(self.call_id)
            return

        # Bestem opkaldets varighed
        call_duration_seconds = self._get_call_length_seconds()

        # Opret køer til agent og caller
        agent_queue = Queue()
        caller_queue = Queue()

        # Dræb eksisterende greenlets i audio_streamer_pool hvis der er nogen
        if len(self.audio_streamer_pool) > 0:
            logging.warning(
                "audio_streamer_pool er ikke tom, dræber eksisterende greenlets..."
            )
            self.audio_streamer_pool.kill()

        # Start greenlets til at enqueue data og processere køer
        self.audio_streamer_pool.spawn(
            self._enqueue_data, [agent_queue, caller_queue], call_duration_seconds
        )
        self.audio_streamer_pool.spawn(
            self._process_queue,
            agent_queue,
            "agent",
            audio_streamer_webservice_client,
        )
        self.audio_streamer_pool.spawn(
            self._process_queue,
            caller_queue,
            "caller",
            audio_streamer_webservice_client,
        )

        # Vent til opkaldet er færdigt og transskriberinger er uploadet
        self.audio_streamer_pool.join()

        if not MOCK_PROCESS_CALL:
            # Kald /process_call endpoint
            self.audio_streamer_pool.spawn(
                audio_streamer_webservice_client.process_call
            )
        else:
            # Kald health-check som mock og sæt flag ved success
            def mock_process_call():
                health_check_success = audio_streamer_webservice_client.health_check()
                if health_check_success:
                    self.fetched_notat_event.set()
                else:
                    logging.error(f"/health-check fejlede")

            self.audio_streamer_pool.spawn(mock_process_call)

        # Vent til frontenden har hentet notatet, eller timeout efter 60 sekunder
        success = self.fetched_notat_event.wait(timeout=60)

        self.fetch_notat_time = time.perf_counter()

        if not success:
            logging.error(
                f"Timeout i at vente på at FE hentede notat for call_id: {self.call_id}"
            )

        # Log svartiden fra opkaldets afslutning til notatet er hentet af FE
        self.environment.events.request.fire(
            request_type="N/A",
            name="total_response_time",
            response_time=int((self.fetch_notat_time - self.end_call_time) * 1000),
            response_length=0,
            exception=None if success else TimeoutError("FE fetch notat timeout"),
        )

    def simulate_fe(self):
        """
        Simulerer at kunderådgiveren har frontend-siden åben, som løbende tjekker
        for opkaldsstatus og henter notatet når opkaldet er færdigt.

        Denne metode kører i en separat greenlet for hver bruger.
        """

        POLL_INTERVAL_FAST = 10
        POLL_INTERVAL_SLOW = 60
        POLL_INTERVAL_END_CALL = 2
        SLOW_POLL_THRESHOLD = 15 * 60
        END_CALL_THRESHOLD = 20

        last_seen_msg = ""
        fe_webservice_client = FrontendWebserviceClient(self._get_user_context())
        start_time = time.perf_counter()

        while not self.stopped:

            # Hent status fra /fetch_status endpoint
            status = fe_webservice_client.fetch_status(last_seen_msg=last_seen_msg)

            if status is None:
                logging.error(f"Fejl ved hentning af status fra /fetch_status")
                gevent.sleep(POLL_INTERVAL_FAST)
                continue

            # Nulstil startTime hvis der er ny status
            if last_seen_msg != status:
                start_time = time.perf_counter()

            time_since_last_change = time.perf_counter() - start_time

            if status == "end-summary" and last_seen_msg != "end-summary":
                # Hent notat fra /get_notat endpoint
                notat, call_id = fe_webservice_client.get_notat()

                if notat and call_id and call_id == self.call_id:
                    # Sæt event for hentning af notat
                    self.fetched_notat_event.set()

                    # Send feedback
                    fe_webservice_client.feedback(
                        call_id=call_id,
                        agent_id=self.agent_id or "",
                        feedback=f"loadtest_{self.timestamp}: Skide godt notat!",
                        rating=-1,
                        benyttet=1,
                    )

            # Opdater last_seen_msg
            last_seen_msg = status

            # Bestem polling interval baseret på status og tid
            if time_since_last_change > SLOW_POLL_THRESHOLD:
                # Hvis der er gået mere end 15 minutter, poll hvert minut
                poll_interval = POLL_INTERVAL_SLOW
            elif status == "end-call" and time_since_last_change <= END_CALL_THRESHOLD:
                # Hvis status er end-call, poll hvert 2. sekund de første 20 sekunder
                poll_interval = POLL_INTERVAL_END_CALL
            else:
                # Normal polling hver 10. sekund
                poll_interval = POLL_INTERVAL_FAST

            # Vent før næste polling
            gevent.sleep(poll_interval)

    def _get_user_context(self) -> UserContext:
        return UserContext(
            client=self.client,
            config=self.config,
            timestamp=self.timestamp,
            call_id=self.call_id,
            agent_id=self.agent_id,
            koe_id=self.koe_id,
            cpr=self.cpr,
        )

    def _build_transcriptions_jsonl(self, transcription_results: list[dict]) -> str:
        """Byg en JSONL streng fra transskriberingsresultaterne."""

        jsonl_data = ""
        # Sorter resultater efter timestamp før opbygning af JSONL
        sorted_results = sorted(
            transcription_results, key=lambda x: x.get("timestamp", 0)
        )
        line_data_start = {
            "status": "start",
            "call_id": self.call_id,
            "agent_id": self.agent_id,
            "koe_id": self.koe_id,
            "cpr": self.cpr,
            "time": dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "sentence": "",
        }

        jsonl_data += json.dumps(line_data_start, ensure_ascii=False) + "\n"
        for result in sorted_results:
            line_data = {
                "type": "transcript",
                "call_id": self.call_id,
                "agent_id": self.agent_id,
                "speaker": result.get("speaker"),
                "timestamp": result.get("timestamp"),
                "time": dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "sentence": result.get("text"),
                "queue_id": self.koe_id,
                "cpr": self.cpr,
            }
            try:
                jsonl_data += json.dumps(line_data, ensure_ascii=False) + "\n"
            except Exception as json_e:
                logging.error(
                    f"Fejl ved konvertering af resultat til JSON: {result} - {json_e}"
                )
                continue

        line_data_end = {
            "status": "end",
            "call_id": self.call_id,
            "agent_id": self.agent_id,
            "koe_id": self.koe_id,
            "cpr": self.cpr,
            "time": dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "sentence": "",
        }

        jsonl_data += json.dumps(line_data_end, ensure_ascii=False) + "\n"

        return jsonl_data

    @staticmethod
    def _get_call_length_seconds() -> float:
        """
        Returner en tilfældig opkaldslængde i sekunder inden for de
        specificerede grænser.
        """
        durations = list(CALL_DURATION_RANGES.values())
        weights = list(CALL_DURATION_WEIGHTS.values())
        selected_range = random.choices(durations, weights=weights, k=1)[0]
        return random.uniform(selected_range[0], selected_range[1])

    def _enqueue_data(self, queues: list[Queue], call_duration_seconds: float) -> None:
        """
        Smid data i de angivne køer hver 30. sekund indtil opkaldet er færdigt.
        """

        start_time = time.perf_counter()
        stop_time = start_time + call_duration_seconds
        next_enqueue_time = start_time
        done = False
        while not done:
            if stop_time - next_enqueue_time > 30:
                next_enqueue_time += 30
            else:
                next_enqueue_time = stop_time
                done = True
            sleep_duration = max(0, next_enqueue_time - time.perf_counter())
            gevent.sleep(sleep_duration)
            for queue in queues:
                # 0 = lyddata, 1 = opkald færdigt
                queue.put(0 if not done else 1)

        self.end_call_time = time.perf_counter()

        # Fjern call_id fra aktive opkald
        if hasattr(self.environment, "active_calls") and isinstance(
            self.environment.active_calls, set
        ):
            self.environment.active_calls.discard(self.call_id)

    def _process_queue(
        self,
        queue: Queue,
        speaker: str,
        audio_streamer_webservice_client: AudioStreamerWebserviceClient,
    ) -> None:
        """
        Processér lyddata i køen, transskribér løbende og upload til sidst
        transskriberinger til Blob Storage.
        """

        storage_account_client = AzureStorageAccountClient(self._get_user_context())
        openai_transcriber_client = AzureOpenAITranscriberClient(
            self._get_user_context(),
            speaker=speaker,
            mock_transcription=MOCK_TRANSCRIPTION,
        )

        # Send start-call status
        storage_account_client.send_status_to_queue(
            "start-call", audio_streamer_webservice_client
        )

        transcription_results = []

        # Processér og transskribér data i køen
        while True:
            item = queue.get()
            if item == 0:
                # Transskribér
                result = openai_transcriber_client.transcribe(
                    audio_bytes=self.audio_bytes,
                    filename=os.path.basename(self.audio_path),
                )
                if result is not None:
                    transcription_results.append(result)
            elif item == 1:
                break

        # Send end-call status
        storage_account_client.send_status_to_queue(
            "end-call", audio_streamer_webservice_client
        )

        # Transskribér sidste lyd
        result = openai_transcriber_client.transcribe(
            audio_bytes=self.audio_bytes,
            filename=os.path.basename(self.audio_path),
        )
        if result is not None:
            transcription_results.append(result)

        # Upload transskribering til blob storage
        if transcription_results:

            jsonl_data = self._build_transcriptions_jsonl(transcription_results)

            if jsonl_data:
                # Definer blob-navn - inkluder taleren i filnavnet
                blob_name = f"transcriptions-{self.call_id}-{speaker}.jsonl"

                # Upload JSONL-dataene
                upload_success = storage_account_client.upload_to_blob(
                    blob_name,
                    jsonl_data,
                    audio_streamer_webservice_client,
                )
                if not upload_success:
                    logging.error(
                        f"Kunne ikke uploade transskriberingsblob: {blob_name}"
                    )
        else:
            logging.warning(
                f"Ingen transskriberingsresultater for call_id: {self.call_id}, speaker: {speaker}"
            )
