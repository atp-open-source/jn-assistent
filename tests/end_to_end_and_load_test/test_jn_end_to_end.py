# Vores end-to-end-test bruger CoRaL-datasættet som testdata
# @dataset{coral2024,
#   author    = {Dan Saattrup Nielsen, Sif Bernstorff Lehmann, Simon Leminen Madsen, Anders Jess Pedersen, Anna Katrine van Zee and Torben Blach},
#   title     = {CoRal: A Diverse Danish ASR Dataset Covering Dialects, Accents, Genders, and Age Groups},
#   year      = {2024},
#   url       = {https://hf.co/datasets/alexandrainst/coral},
# }


import contextlib
import json
import os
import queue
import sys
import threading
import time
import traceback
import wave
from datetime import datetime
from timeit import default_timer
from unittest import TestCase
from uuid import uuid4

import numpy as np
import requests
import soundfile as sf
from datasets import Audio, load_dataset
from dotenv import load_dotenv
from loguru import logger

from audio_streamer.config import get_config
from audio_streamer.openai_transcriber import AzureOpenAITranscriber

# Load miløvariabler fra .env
load_dotenv(override=True)

sim_tider = {
    "setup": 0.0,
    "transcription_threads": 0.0,
    "streaming": 0.0,
    "transcription_from_streaming_start": 0.0,
    "transcription_after_streaming_end": 0.0,
    "cleanup_audio_file": 0.0,
    "generating_notes": 0.0,
    "program": 0.0,
}


class EndToEndTestJN:
    """
    Laver en end-to-end test af JN, hvilket indebærer følgende:

        1. Der sendes lyd til transskribering hos GPT4o mini transcribe.
        2. Transskriberinger modtages og sendes til Azure Blob Storage i containeren
           'transcriptions'.
        3. Idet transskriberingerne er uploadet, kaldes /process_call i Leverance for at
           generere et notatudkast.
        4. Det tjekkes, at notatudkastet er genereret.
    """

    def __init__(self, dataset="test", streaming=True, n_files=20, controller_version="onprem"):
        """
        Initialiserer end-to-end testen med konfiguration for lyddata.

        Args:
            dataset: Datasæt til test ("val", "test", "train")
            streaming: Om datasættet skal indlæses som streaming
            n_files: Antal lydfiler at bruge fra datasættet
            controller_version: Controller type ('onprem' eller 'azure')
        """
        self.dataset = dataset
        self.streaming = streaming
        self.n_files = n_files
        self.controller_version = controller_version
        self.agent_id = "TEST"
        self.call_id = f"{uuid4()}-{self.agent_id}"
        self.queue_id = "TEST-KØ"
        self.config = get_config(
            env=os.getenv("ENV", "dev"),
            azure=os.getenv("CONTROLLER_VERSION", "onprem") == "azure",
        )
        self.storage_type = "azure"
        self.has_errors = False
        self.error_messages = []

        # Definér argumenter til OpenAI Transcriber
        self.args = {
            "CallID": self.call_id,
            "AgentID": self.agent_id,
            "Queue": self.queue_id,
            "CPR": "",
        }

        # Opsæt queues og stop event
        self.stop_event = threading.Event()
        self.agent_queue = queue.Queue()
        self.caller_queue = queue.Queue()

        # Stier til midlertidige filer
        self.temp_dir = os.path.join(os.path.expanduser("~"), "test_temp")
        os.makedirs(self.temp_dir, exist_ok=True)
        self.audio_filename = os.path.join(self.temp_dir, f"coral_sample_{self.agent_id}.wav")
        self.combined_file_name = os.path.join(
            self.temp_dir, f"output_combined_{self.agent_id}.wav"
        )

        # Log at end-to-end test er initialiseret
        logger.info(
            f"[JN END-TO-END-TEST INFO]: End-To-End Test initialiseret for call_id: {self.call_id} med controller_version: '{self.controller_version}'"
        )
        logger.info(f"[JN END-TO-END-TEST INFO]: Test konfiguration - config {self.config}")

    def _log_error(self, error_msg: str):
        """
        Log fejl og track fejlbeskeder.
        Args:
            error_msg: Fejlbesked der skal logges
        """
        self.has_errors = True
        full_error_msg = f"{error_msg} [controller_version: {self.controller_version}]"
        self.error_messages.append(full_error_msg)
        logger.error(f"[JN END-TO-END-TEST ERROR]: {full_error_msg}")

    def simulate_audio_streaming(self):
        """
        Simulerer streaming af lyd fra CoRal datasættet til transskriberingsmodellen GPT4o-mini-transcribe.
        Denne metode udfører følgende trin:

            1. Indlæser CoRal datasættet.
            2. Kombinerer n_files lydfiler til én fil.
            3. Opretter OpenAI Transcriber instanser for agent og caller.
            4. Streamer lyddata til transcriber instances via queues.
            5. Venter på at transskribering er færdig.
            6. Sender start-call og end-call events til Azure Queue.

        Returns:
            bool: True hvis testen blev udført succesfuldt, ellers False

        Raises:
            RuntimeError: Ved fejl i testen, så pipeline afbrydes
        """
        agent_thread = None
        caller_thread = None

        timer_start_setup = default_timer()

        try:
            logger.info(
                f"[JN END-TO-END-TEST INFO]: Loader lyd til simulering af lydstreaming for call-id '{self.call_id}'"
            )

            # Load CoRal dataset
            common_voice = self.load_coral_data()

            # Kombinér til én lydfil
            sample = list(common_voice[self.dataset].take(self.n_files))

            # Loop gennem alle lydfilerne og gem dem i den kombinerede lydfil
            for _idx, s in enumerate(sample):
                audio = s["audio"]["array"]
                sample_rate = s["audio"]["sampling_rate"]
                sf.write(self.audio_filename, audio, sample_rate)

                if os.path.exists(self.combined_file_name):
                    self.append_two_wavs(
                        self.combined_file_name,
                        self.audio_filename,
                        self.combined_file_name,
                    )
                else:
                    sf.write(self.combined_file_name, audio, sample_rate)

                os.remove(self.audio_filename)

        except Exception as e:
            error_msg = (
                f"Fejl under indlaesning af CoRal datasaet eller kombination af lydfiler: {e}"
            )
            self._log_error(error_msg)
            raise RuntimeError(error_msg) from e

        try:
            # Hent config
            config, streamer_version = self._fetch_config()

            # Kontrollér at config og streamer_version er hentet korrekt
            if not config or not streamer_version:
                error_msg = (
                    f"Kunne ikke hente Config eller 'streamer-version' for call-id '{self.call_id}'"
                )
                self._log_error(error_msg)
                raise RuntimeError(error_msg)

            logger.info(
                f"[JN END-TO-END-TEST INFO]: Starter transskribering for call-id {self.call_id} med streamer_version '{streamer_version}'"
            )

            # Initialisér OpenAI Transcriber instanser for agent og caller
            try:
                agent_transcriber = AzureOpenAITranscriber(
                    self.args, config, "agent", self.controller_version
                )
                caller_transcriber = AzureOpenAITranscriber(
                    self.args, config, "caller", self.controller_version
                )
            except Exception as e:
                error_msg = (
                    f"Kunne ikke initialisere OpenAI Transcriber for call-id '{self.call_id}': {e}"
                )
                self._log_error(error_msg)
                raise RuntimeError(error_msg) from e

            # Beregner tid der bruges på setup af test og som ikke ville ske ved hvert enkelt kald i produktion
            timer_end_setup = default_timer()
            sim_tider["setup"] += timer_end_setup - timer_start_setup

            timer_start_transcription_threads = default_timer()

            # Start transskribering
            try:
                agent_thread = threading.Thread(
                    target=self._transcriber_wrapper,
                    args=(
                        agent_transcriber,
                        self.agent_queue,
                        self.stop_event,
                        "agent",
                    ),
                )
                caller_thread = threading.Thread(
                    target=self._transcriber_wrapper,
                    args=(
                        caller_transcriber,
                        self.caller_queue,
                        self.stop_event,
                        "caller",
                    ),
                )

                # Sæt tråde som daemon-tråde, så de afsluttes når hovedtråden afsluttes uanset hvad
                agent_thread.daemon = True
                caller_thread.daemon = True

                # Start transskriberingstrådene for agent og caller
                agent_thread.start()
                caller_thread.start()

            except Exception as e:
                error_msg = (
                    f"Fejl under start af transskriberingstråde for call-id '{self.call_id}': {e}"
                )
                self._log_error(error_msg)
                raise RuntimeError(error_msg) from e

            # Stream lyd til køen
            logger.info(
                f"[JN END-TO-END-TEST INFO]: Starter streaming af lyd for call-id '{self.call_id}'"
            )

            # Beregner tid der bruges på at starte transskriberings tråde
            timer_end_transcription_threads = default_timer()
            sim_tider["transcription_threads"] += (
                timer_end_transcription_threads - timer_start_transcription_threads
            )

            timer_start_streaming = default_timer()

            try:
                # Åbn den kombinerede lydfil
                with wave.open(self.combined_file_name, "rb") as wav_file:
                    # Udtræk metadata fra lydfilen
                    channels = wav_file.getnchannels()
                    sample_width = wav_file.getsampwidth()
                    frame_rate = wav_file.getframerate()

                    # Læg metadata i køen for agent og caller med status=start
                    start_metadata = self._create_metadata(
                        "start", channels, sample_width, frame_rate, "agent"
                    )
                    self.agent_queue.put(json.dumps(start_metadata))
                    start_metadata["speaker"] = "caller"
                    self.caller_queue.put(json.dumps(start_metadata))

                    # Loop igennem lydfilen og læs i chunks (16KB chunks)
                    chunk_size = 1024 * 16
                    while True:
                        audio_chunk = wav_file.readframes(chunk_size)
                        if not audio_chunk:
                            break

                        # Læg lydchunks i kø for både agent og caller
                        self.agent_queue.put(audio_chunk)
                        self.caller_queue.put(audio_chunk)

                        time.sleep(0.01)

                    # Når streaming af lyd er færdig sendes afsluttende metadata status=end for både agent og caller
                    end_metadata = self._create_metadata(
                        "end", channels, sample_width, frame_rate, "agent"
                    )
                    self.agent_queue.put(json.dumps(end_metadata))
                    end_metadata["speaker"] = "caller"
                    self.caller_queue.put(json.dumps(end_metadata))

                # Beregner tid der bruges på at streame lyd til køen
                timer_end_streaming = default_timer()
                sim_tider["streaming"] += timer_end_streaming - timer_start_streaming

                # Beregn længden af lyden og log
                duration = self.get_audio_duration(self.combined_file_name)
                logger.info(
                    f"[JN END-TO-END-TEST INFO]: Total laengde paa lyd: {duration:.2f} sekunder for call-id {self.call_id}"
                )

            except Exception as e:
                error_msg = f"Fejl under streaming af lyddata for call-id '{self.call_id}': {e}"
                self._log_error(error_msg)
                self.stop_event.set()
                if agent_thread:
                    agent_thread.join(timeout=2)
                if caller_thread:
                    caller_thread.join(timeout=2)
                raise RuntimeError(error_msg) from e

            # Afvent transskribering af lyden
            wait_start = time.time()
            timeout_seconds = max(duration * 1.5, 30)

            while (time.time() - wait_start) < timeout_seconds:
                if self.agent_queue.empty() and self.caller_queue.empty():
                    logger.info(
                        f"[JN END-TO-END-TEST INFO]: Alle lydsegmenter er transskriberet for call-id '{self.call_id}'."
                    )
                    break
                time.sleep(1)

            if not (self.agent_queue.empty() and self.caller_queue.empty()):
                error_msg = (
                    f"Timeout under afventning af transskribering for call-id '{self.call_id}'"
                )
                self._log_error(error_msg)
                self.stop_event.set()
                if agent_thread:
                    agent_thread.join(timeout=2)
                if caller_thread:
                    caller_thread.join(timeout=2)
                raise RuntimeError(error_msg)

            # Signalér stop til transskriberingstrådene
            self.stop_event.set()
            if agent_thread:
                agent_thread.join(timeout=10)
            if caller_thread:
                caller_thread.join(timeout=10)

            # Beregner først tid der bruges på transkribering fra start af streaming
            # og derefter hvor lang tid der er brugt på transkribering efter streaming er afsluttet
            timer_end_transcription = default_timer()
            sim_tider["transcription_from_streaming_start"] += (
                timer_end_transcription - timer_start_streaming
            )
            sim_tider["transcription_after_streaming_end"] += (
                timer_end_transcription - timer_end_streaming
            )

            timer_start_cleanup_audio_file = default_timer()

            # Ryd op, i.e. slet den kombinerede lydfil
            try:
                os.remove(self.combined_file_name)
            except Exception as e:
                logger.warning(
                    f"[JN END-TO-END-TEST INFO]: Kunne ikke slette den kombinerede lydfil for call-id '{self.call_id}': {e}"
                )

            # Beregner tid der bruges på oprydning af test lydfiler
            timer_end_cleanup_audio_file = default_timer()
            sim_tider["cleanup_audio_file"] += (
                timer_end_cleanup_audio_file - timer_start_cleanup_audio_file
            )

            timer_start_generation_notes = default_timer()
            logger.info(
                f"[JN END-TO-END-TEST INFO]: Simulering af lydstreaming med CoRal lyddata afsluttet for call_id: '{self.call_id}'"
            )

            # Kald Leverance for at generere notatudkast
            self._notify_leverance()

            # Beregner tid der bruges på at generere notatudkast ved at kalde Leverance endpoint
            timer_end_generation_notes = default_timer()
            sim_tider["generating_notes"] += (
                timer_end_generation_notes - timer_start_generation_notes
            )

            # Tjek om der er opstået fejl under testen
            if self.has_errors:
                error_summary = f"Test gennemført med {len(self.error_messages)} fejl: {'; '.join(self.error_messages)}"
                logger.error(f"[JN END-TO-END-TEST ERROR]: {error_summary}")
                raise RuntimeError(error_summary)

            # Beregn total tid for hele testen
            timer_end_program = default_timer()
            sim_tider["program"] += timer_end_program - timer_start_setup
            return True

        except Exception as e:
            # Sæt stop_event for at stoppe trådene
            self.stop_event.set()

            # Vent på trådene, men med timeout for at undgå at hænge
            if agent_thread and agent_thread.is_alive():
                agent_thread.join(timeout=5)
            if caller_thread and caller_thread.is_alive():
                caller_thread.join(timeout=5)

            # Forsøg at slette den kombinerede lydfil hvis den eksisterer
            if os.path.exists(self.combined_file_name):
                with contextlib.suppress(Exception):
                    os.remove(self.combined_file_name)

            # Log fejlen og kast den videre så pipeline bliver afbrudt
            error_msg = f"Fejl under simulate_audio_streaming for call-id '{self.call_id}': {e}"
            self._log_error(error_msg)
            raise RuntimeError(error_msg) from e

    def _transcriber_wrapper(self, transcriber, queue_obj, stop_event, speaker_type):
        """
        Wrapper til transcriber.process_queue som logger fejl.
        Fejl i transcriber.process_queue vil blive logget og vil føre til fejl i end-to-end testen.
        """
        try:
            transcriber.process_queue(queue_obj, stop_event)
        except Exception as e:
            error_msg = f"Fejl i process_queue for speaker '{speaker_type}': {e}"
            self._log_error(error_msg)
            # Sæt stop_event så andre tråde også stopper
            stop_event.set()
            # Markér som fejlet for at sikre, at testen fejler
            self.has_errors = True
            # Raise exception så simulate_audio_streaming kan fange den
            raise RuntimeError(error_msg) from e

    def load_coral_data(self) -> dict:
        """
        Indlæser CoRal datasættet for den angivne splitning.

        Returns:
            dict: Indlæste datasæt
        """
        # Indlæs CoRal datasættet med load_dataset()
        common_voice = {}
        common_voice[self.dataset] = load_dataset(
            "CoRal-project/coral-v2",
            "read_aloud",
            split=self.dataset,
            streaming=self.streaming,
            token=os.getenv("HF_TOKEN"),
        )
        common_voice[self.dataset] = common_voice[self.dataset].cast_column(
            "audio", Audio(sampling_rate=16000)
        )

        return common_voice

    def append_two_wavs(
        self, original_wav_path_1: str, original_wav_path_2: str, output_wav_path: str
    ) -> None:
        """
        Kombinerer to WAV-filer til en enkelt fil.

        Args:
            original_wav_path_1: Sti til den første WAV-fil
            original_wav_path_2: Sti til den anden WAV-fil
            output_wav_path: Sti til den gemte kombinerede WAV-fil
        """
        # Læs de to lydfiler
        audio_1, sample_rate_1 = sf.read(original_wav_path_1)
        audio_2, _ = sf.read(original_wav_path_2)

        # Kombinér de to lydfiler
        combined_audio = np.concatenate((audio_1, audio_2))

        # Gem den endelige kombinerede lydfil
        sf.write(output_wav_path, combined_audio, sample_rate_1)

    def get_audio_duration(self, file_path: str) -> float:
        """
        Beregner varigheden af en lydfil.

        Args:
            file_path: Sti til lydfilen

        Returns:
            float: Varighed i sekunder
        """
        with wave.open(file_path, "r") as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            duration = frames / float(rate)
            return duration

    def _create_metadata(
        self,
        status: str,
        channels: int,
        sample_width: int,
        frame_rate: int,
        speaker: str,
    ) -> dict:
        """
        Opret metadata dict for lydoptagelsen.

        Args:
            status: Status for lydklippet ("start" eller "end")
            channels: Antal kanaler i lydklippet
            sample_width: Sample width for lydklippet
            frame_rate: Frame rate for lydklippet
            speaker: Taler ("agent" eller "caller")

        Returns:
            Dict: Metadata som dict
        """
        return {
            "call_id": self.call_id,
            "agent_id": self.agent_id,
            "koe_id": self.queue_id,
            "status": status,
            "channels": channels,
            "sample_width": sample_width,
            "frame_rate": frame_rate,
            "speaker": speaker,
            "cpr": "",
        }

    def _notify_leverance(self) -> bool:
        """
        Kalder Leverances /process_call endpoint når transskribering er færdig for at generere notatudkast.

        Returns:
            bool: True hvis kald til Leverance lykkedes

        Raises:
            RuntimeError: Hvis kald til Leverance fejler
        """
        try:
            uid = str(uuid4())

            # Vælg korrekt URL baseret på controller_version
            if self.controller_version == "azure":
                process_call_url = self.config.AZURE_URL_PROCESS_CALL
            else:
                process_call_url = self.config.LEVERANCE_URL_PROCESS_CALL

            logger.info(
                f"[JN END-TO-END-TEST INFO]: Kalder Leverance /process_call for call_id: '{self.call_id}' med controller_version '{self.controller_version}'"
            )

            response = requests.get(
                process_call_url,
                params={
                    "call_id": self.call_id,
                    "uid": uid,
                    "storage_type": self.storage_type,
                },
                auth=("jn", os.getenv("LEVERANCE_PASSWORD")),
                verify=False,
            )
            response.raise_for_status()

            logger.info(
                f"[JN END-TO-END-TEST INFO]: "
                f"Leverance blev kaldt paa '{process_call_url}' "
                f"for call_id '{self.call_id}' med uid {uid}. "
                f"Statuskode: {response.status_code}"
            )
            return True

        except Exception as e:
            error_msg = (
                f"Fejl ved kald til Leverance paa '{process_call_url}' "
                f"for call-id '{self.call_id}': {e}"
            )
            self._log_error(error_msg)
            raise RuntimeError(error_msg) from e

    def _fetch_config(self):
        """
        Kalder Leverance endpoint /get_config for at hente konfigurationen for TEST-agenten.

        Returns:
            Tuple[object, str]: Configobjekt og streamer-version

        Raises:
            RuntimeError: Hvis konfigurationen ikke kan hentes
        """
        try:
            # Kald leverance for at hente konfigurationen
            config_location_url = f"{self.config.LEVERANCE_URL}/get_config"
            logger.info(
                f"[JN END-TO-END-TEST INFO]: Henter config for call-id '{self.call_id}' fra: {config_location_url}"
            )
            config_location = requests.get(
                config_location_url,
                params={
                    "kr_initialer": self.agent_id,
                    "uid": self.call_id,
                },
                verify=False,
                timeout=10,
            )
            config_location.raise_for_status()

            # Parse JSON svar fra Leverance
            config_data = config_location.json()
            logger.info(
                f"[JN END-TO-END-TEST INFO]: Modtog konfiguration for call-id {self.call_id}: {config_data}"
            )

            # Hent miljø
            if "miljoe" not in config_data:
                raise KeyError(
                    f"[JN END-TO-END-TEST INFO]: 'miljoe' mangler i konfiguration i jn.config for call-id {self.call_id}."
                )
            miljoe = config_data["miljoe"].lower()
            logger.info(
                f"[JN END-TO-END-TEST INFO]: Miljoe specificeret for agent {self.agent_id} i jn.config: {miljoe}"
            )

            # Hent config baseret på miljø
            config = get_config(env=miljoe)
            logger.info(
                f"[JN END-TO-END-TEST INFO]: Konfiguration hentet for call-id {self.call_id}: {self.config}"
            )

            # Hent streamer-version
            streamer_version = config_data.get("streamer_version", "openai").lower()
            if streamer_version != "openai":
                logger.warning(
                    f"[JN END-TO-END-TEST INFO]: Ugyldig streamer_version '{streamer_version}' specificeret i konfiguration i jn.config."
                )

            return config, streamer_version

        except requests.exceptions.RequestException as e:
            error_msg = f"Kunne ikke hente config fra '{config_location_url}' for call-id '{self.call_id}'. Fejlbesked: {e}."
            self._log_error(error_msg)
            raise RuntimeError(error_msg) from e

        except json.JSONDecodeError as e:
            error_msg = f"Kunne ikke parse svar fra Leverance endpoint '{config_location_url}' for call-id '{self.call_id}'."
            self._log_error(error_msg)
            raise RuntimeError(error_msg) from e

        except Exception as e:
            error_msg = f"Der opstod en fejl med at hente config for call-id '{self.call_id}'. Fejlbesked: {e}."
            self._log_error(error_msg)
            raise RuntimeError(error_msg) from e

    def performance_summary(self) -> str:
        """
        Genererer en opsummering af ydeevnen for end-to-end testen.

        Returns:
            str: Opsummering af ydeevnen
        """
        return (
            f"Kørselstid for hele testen: {sim_tider['program']:.2f} sekunder\n"
            f"Kørselstid for hele testen uden setup: {sim_tider['program'] - sim_tider['setup']:.2f} sekunder\n"
            f"Kørselstid for setup af testdata: {sim_tider['setup']:.2f} sekunder\n"
            f"Kørselstid for opsætning af transskriberings tråde: {sim_tider['transcription_threads']:.2f} sekunder\n"
            f"Kørselstid for streaming af kald til queue: {sim_tider['streaming']:.2f} sekunder\n"
            f"Kørselstid for transskribering med streaming: {sim_tider['transcription_from_streaming_start']:.2f} sekunder\n"
            f"Kørselstid for transskribering efter streaming: {sim_tider['transcription_after_streaming_end']:.2f} sekunder\n"
            f"Kørselstid for generering af notatudkast: {sim_tider['generating_notes']:.2f} sekunder\n"
            f"Kørselstid for oprydning af lydfiler: {sim_tider['cleanup_audio_file']:.2f} sekunder\n"
        )


def main():
    exit_code = 0
    error_occurred = False

    # Tjek om CONTROLLER_VERSION er sat i miljøvariablerne
    env_controller_version = os.getenv("CONTROLLER_VERSION")

    # Kør end-to-end test for den specificerede controller_version eller for begge hvis ikke sat
    if env_controller_version:
        controller_versions = [env_controller_version.lower()]
        logger.info(
            f"[JN END-TO-END-TEST INFO]: Kører end-to-end test for controller_version: '{env_controller_version}' (fra miljøvariabel)"
        )
    else:
        controller_versions = ["onprem", "azure"]
        logger.info(
            "[JN END-TO-END-TEST INFO]: Kører test for alle controller_versions: onprem og azure"
        )

    # Kør end-to-end test for hver controller_version og gem resultater
    test_results = {}
    try:
        for controller_version in controller_versions:
            logger.info(
                f"\n{'='*80}\n"
                f"[JN END-TO-END-TEST INFO]: Starter end-to-end test med controller_version: '{controller_version}'\n"
                f"{'='*80}\n"
            )

            # Log starttid
            start_time = datetime.now()

            try:
                # Initialisér EndToEndTestJN med den specifikke controller_version
                e2e_test = EndToEndTestJN(
                    dataset="test",
                    streaming=True,
                    n_files=20,
                    controller_version=controller_version,
                )

                # Kør testen
                success = e2e_test.simulate_audio_streaming()
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()

                # Gem testresultat
                test_results[controller_version] = {
                    "success": success and not e2e_test.has_errors,
                    "duration": duration,
                    "errors": e2e_test.error_messages,
                }

                if not success:
                    logger.error(
                        f"[JN END-TO-END-TEST ERROR]: End-to-end test fejlede for controller_version '{controller_version}'."
                    )
                    error_occurred = True

                elif e2e_test.has_errors:
                    logger.error(
                        f"[JN END-TO-END-TEST ERROR]: End-to-end test gennemført med fejl for controller_version '{controller_version}'."
                    )
                    error_occurred = True

                else:
                    logger.info(
                        f"[JN END-TO-END-TEST INFO]: JN End-To-End Test gennemfoert succesfuldt for controller_version '{controller_version}' paa {duration:.2f} sekunder"
                    )
                    perf_summary = e2e_test.performance_summary()
                    logger.info(f"[JN END-TO-END-TEST INFO]: Performance summary: \n{perf_summary}")

            except Exception as e:
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                error_msg = f"Fejl under test af controller_version '{controller_version}': {e}"
                logger.error(f"[JN END-TO-END-TEST ERROR]: {error_msg}")
                logger.error(f"[JN END-TO-END-TEST ERROR]: Traceback: {traceback.format_exc()}")

                # Gem testresultat for fejlet test
                test_results[controller_version] = {
                    "success": False,
                    "duration": duration,
                    "errors": [error_msg],
                }
                error_occurred = True

        # Print det samlede resultat
        print("\n" + "=" * 80)
        print("SAMLET RESULTAT FOR JN END-TO-END TEST")
        print("=" * 80)
        all_passed = True
        for controller_version, result in test_results.items():
            status = "[PASSED]" if result["success"] else "[FAILED]"
            print(
                f"{controller_version.upper()}: {status} (Varighed: {result['duration']:.2f} sekunder)"
            )
            if not result["success"]:
                all_passed = False
                if result["errors"]:
                    print(f"  Fejl: {', '.join(result['errors'])}")
        print("=" * 80)

        if all_passed:
            print("\nAlle tests gennemfoert succesfuldt uden fejl!")
            exit_code = 0
        else:
            print("\nEn eller flere tests fejlede!")
            exit_code = 1
            error_occurred = True

    except Exception as e:
        logger.error(f"[JN END-TO-END-TEST ERROR]: Fejl under koersel af JN End-To-End Test: {e}")
        logger.error(f"[JN END-TO-END-TEST ERROR]: Traceback: {traceback.format_exc()}")
        error_occurred = True
        exit_code = 1

    finally:
        if error_occurred:
            print("JN End-To-End Test fejlede!")
            logger.error("[JN END-TO-END-TEST ERROR]: Test afsluttet med fejl.")

        sys.exit(exit_code)


class TestEndToEndJN(TestCase):
    """
    Testklasse for at køre end-to-end testen for JN i build pipeline.
    """

    def test_end_to_end_jn(self):
        """
        Kører end-to-end testen for JN.
        """
        main()


if __name__ == "__main__":
    main()
