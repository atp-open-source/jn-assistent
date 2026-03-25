import io, json, os, queue, sys, threading, time
from typing import Any, Dict, List, Union
from pydantic import BaseModel
from loguru import logger
from uuid import uuid4

# Tilføj imports til systembakkeikon
import win32gui
import win32con

from audio_streamer.config import BaseConfig, get_config, Metadata
from audio_streamer.tray_icon import TrayIcon
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Opsæt logging
logger.debug("Setting up logger with loguru")
logger.add(
    os.path.join(os.path.expanduser("~"), "jn_audiostreamer.log"),
    rotation="5 MB",
    level="INFO",
)
# Ikon til systembakken
tray_icon = None


def hide_console_window():
    """
    Skjul konsolvinduet, når den kører som en eksekvérbar.
    """
    try:
        # Find vindue ved specifik vinduestitel
        hwnd = win32gui.FindWindow(
            None, r"C:\Program Files (x86)\ATP AudioStreamer\audio_streamer.exe"
        )
        # Vindue ikke fundet, prøv at finde efter klasse
        if hwnd == 0:
            hwnd = win32gui.FindWindow("ConsoleWindowClass", None)

        if hwnd != 0:
            win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
        else:
            logger.warning(f"Kunne ikke finde vinduet audio_streamer.exe")
    except Exception as e:
        logger.exception(f"Der opstod en fejl med at skjule konsolvindue: {e}")


def exit_app(icon):
    """
    Luk programmet.
    """
    icon.stop()
    os._exit(0)


class CommandArgs(BaseModel):
    """
    Klasse til kommandolinje-argumenter.
    """

    startRecording: bool = False
    AgentID: str
    CallID: str
    Queue: str
    CPR: str = ""
    ENV: str = "prod"


class AudioRecorder:
    """
    Basisklasse for selve lydoptagelsen.
    """

    def __init__(
        self, stop_event: threading.Event, data_queue: queue.Queue, args: Dict[str, Any]
    ):
        """
        Initialisér lydoptager.

        Argumenter:
            stop_event: Event der signalerer hvornår optagelsen skal stoppe
            data_queue: Kø til lyddata
            args: Kommandolinje-argumenter
        """
        self.stop_event = stop_event
        self.queue = data_queue
        self.args = args
        self.call_id = args["CallID"]
        self.chunk_size = 1024
        self.kb_stoerelse = 500
        self.max_buffer_size = self.kb_stoerelse * self.chunk_size
        self.max_tid_uden_lyd = 30

    def _create_metadata(
        self,
        status: str = "start",
        channels: int = 1,
        sample_width: int = 2,
        frame_rate: int = 44100,
        speaker: str = "agent",
    ) -> str:
        """
        Opret metadata dict for lydoptagelsen.
        """
        return Metadata(
            call_id=self.args["CallID"],
            agent_id=self.args["AgentID"],
            koe_id=self.args["Queue"],
            status=status,
            channels=channels,
            sample_width=sample_width,
            frame_rate=frame_rate,
            speaker=speaker,
            cpr=self.args.get("CPR", ""),
        ).model_dump_json()

    def start(self) -> None:
        """
        Start optagelse af lyd. Skal implementeres af underklasser.
        """
        raise NotImplementedError("Subklasser skal implementere start()")


class MicrophoneRecorder(AudioRecorder):
    """
    Optager lyd fra mikrofonen.
    """

    def start(self) -> None:
        """
        Start optagelse af lyd.
        """
        from pyaudio import PyAudio, paInt16, paContinue

        FORMAT = paInt16
        CHANNELS = 1
        RATE = 44100
        SAMPLE_WIDTH = 2

        # Fjern CPR fra logging
        args_log = self.args.copy()
        args_log.pop("CPR", None)

        logger.info(
            f"Call_id {self.call_id}: Starter optagelse fra mikrofon: {args_log}"
        )

        # Send indledende metadata
        metadata = self._create_metadata(
            status="start",
            channels=CHANNELS,
            sample_width=SAMPLE_WIDTH,
            frame_rate=RATE,
            speaker="agent",
        )
        self.queue.put(metadata)

        try:
            p = PyAudio()

            # Buffer til at holde indkommende lyddata
            buffer = io.BytesIO()

            tid_siden_sidste_lyd = 0.0

            # Callback-funktion til at håndtere indkommende lyddata i non-blocking mode
            def callback(in_data, frame_count, time_info, status):
                # Spring over hvis stop_event er sat
                if self.stop_event.is_set():
                    return None, paContinue

                try:
                    buffer.write(in_data)
                    if buffer.tell() >= self.max_buffer_size:
                        lyd = buffer.getvalue()
                        # Vi tjekker om der ikke er kommet noget lyd ind
                        if max(lyd) == min(lyd):
                            tid_siden_sidste_lyd += len(lyd) / (
                                RATE * CHANNELS * SAMPLE_WIDTH
                            )
                            if tid_siden_sidste_lyd >= self.max_tid_uden_lyd:
                                tray_icon.notify(
                                    "Ingen lyd fra mikrofonen de sidste 30 sekunder. Tjek lydindstillinger",
                                    "Journalnotatsassistenten",
                                )
                            tid_siden_sidste_lyd = 0.0

                        # Skriv lyddata til køen
                        self.queue.put(lyd)
                        # Ryd bufferen
                        buffer.seek(0)
                        buffer.truncate(0)
                except Exception as e:
                    logger.exception(
                        f"Call_id {self.call_id}: Fejl i callback for mikrofon stream: {e}"
                    )
                return None, paContinue

            # Start stream til mikrofonoptagelse i non-blocking mode
            microphone_stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=self.chunk_size,
                stream_callback=callback,
            )

            logger.info(f"Call_id {self.call_id}: Optagelse fra mikrofon er startet.")

            # Vent på at stop_event er sat
            self.stop_event.wait()
            logger.info(f"Call_id {self.call_id}: Stopper optagelse fra mikrofon.")

            # Sikr at eventuelle resterende data sendes
            if buffer.tell() > 0:
                self.queue.put(buffer.getvalue())
                logger.info(
                    f"Call_id {self.call_id}: Resterende mikrofonlyd blev sendt til køen."
                )

        except Exception as e:
            logger.exception(
                f"Call_id {self.call_id}: Fejl i optagelse fra mikrofonen: {e}"
            )
        finally:
            metadata = self._create_metadata(
                status="end",
                channels=CHANNELS,
                sample_width=SAMPLE_WIDTH,
                frame_rate=RATE,
                speaker="agent",
            )
            self.queue.put(metadata)
            logger.info(f"Call_id {self.call_id}: Stopper optagelse fra mikrofon.")
            try:
                microphone_stream.stop_stream()
                microphone_stream.close()
                p.terminate()
            except Exception as e:
                logger.exception(
                    f"Call_id {self.call_id}: Fejl ved afslutning af mikrofonoptagelse: {e}"
                )

            logger.info(
                f"Call_id {self.call_id}: Optagelse fra mikrofonen er afsluttet."
            )


class SpeakerRecorder(AudioRecorder):
    """
    Optager lyd fra højttalere (borgers lyd).
    """

    def get_speakers_info(self) -> Dict[str, Any]:
        """
        Hent enhedsinformation om højttalere.
        """
        from pyaudiowpatch import PyAudio, paWASAPI

        with PyAudio() as p:
            wasapi_info = p.get_host_api_info_by_type(paWASAPI)

            default_speakers = p.get_device_info_by_index(
                wasapi_info["defaultOutputDevice"]
            )

            loopback_device = None
            for device in p.get_loopback_device_info_generator():
                if default_speakers["name"] in device["name"]:
                    loopback_device = device
                    break
            return loopback_device

    def start(self) -> None:
        """
        Start optagelse af lyd fra højttalere ved hjælp af sounddevice.
        """
        from pyaudiowpatch import PyAudio, get_sample_size, paInt16, paWASAPI
        from pyaudio import paContinue

        # Fjern CPR fra logging
        args_log = self.args.copy()
        args_log.pop("CPR", None)

        logger.info(f"Call_id {self.call_id}: Starter højttaleroptagelse: {args_log}")

        try:
            with PyAudio() as p:
                speaker_info = self.get_speakers_info()
                channels = speaker_info["maxInputChannels"]
                frame_rate = int(speaker_info["defaultSampleRate"])
                sample_size = get_sample_size(paInt16)

                # Send indledende metadata
                metadata = self._create_metadata(
                    status="start",
                    channels=channels,
                    sample_width=sample_size,
                    frame_rate=frame_rate,
                    speaker="caller",
                )
                self.queue.put(metadata)

                # Buffer til at holde indkommende lyddata
                buffer = io.BytesIO()

                # Callback-funktion til at håndtere indkommende lyddata i non-blocking mode
                def callback(in_data, frame_count, time_info, status):
                    # Spring over hvis stop_event er sat
                    if self.stop_event.is_set():
                        return None, paContinue

                    try:
                        buffer.write(in_data)
                        if buffer.tell() >= self.max_buffer_size:
                            lyd = buffer.getvalue()
                            # Skriv lyddata til køen
                            self.queue.put(lyd)
                            # Ryd bufferen
                            buffer.seek(0)
                            buffer.truncate(0)
                    except Exception as e:
                        logger.exception(
                            f"Call_id {self.call_id}: Fejl i callback for højttaler stream: {e}"
                        )
                    return None, paContinue

                # Start stream til højttaleroptagelse i non-blocking mode
                stream = p.open(
                    format=paInt16,
                    channels=channels,
                    rate=frame_rate,
                    frames_per_buffer=self.chunk_size,
                    input_device_index=speaker_info["index"],
                    input=True,
                    stream_callback=callback,
                )

                logger.info(
                    f"Call_id {self.call_id}: Optagelse af højttaler er startet."
                )

                # Vent på at stop_event er sat
                self.stop_event.wait()

                logger.info(
                    f"Call_id {self.call_id}: Stopper optagelse fra højttalere (borger)."
                )

                # Sikr at eventuelle resterende data sendes
                if buffer.tell() > 0:
                    self.queue.put(buffer.getvalue())
                    logger.info(
                        f"Call_id {self.call_id}: Resterende højttalerlyd blev sendt til køen."
                    )

        except Exception as e:
            logger.exception(f"Call_id {self.call_id}: Fejl i højttaleroptagelse: {e}")
        finally:
            metadata = self._create_metadata(
                status="end",
                channels=channels,
                sample_width=sample_size,
                frame_rate=frame_rate,
                speaker="caller",
            )
            self.queue.put(metadata)
            logger.info(
                f"Call_id {self.call_id}: Afslutter optagelse fra højttaler (borger)"
            )
            try:
                stream.stop_stream()
                stream.close()
            except Exception as e:
                logger.exception(
                    f"Call_id {self.call_id}: Der opstod en fejl med at afslutte højttaleroptagelse: {e}"
                )

            logger.info(f"Call_id {self.call_id}: Højttaleroptagelse er afsluttet.")


def parse_args(args: List[str]) -> CommandArgs:
    """
    Parsér kommandolinje-argumenter.

    Argumenter:
        args: Kommandolinje-argumenter

    Returnerer:
        Parsede argumenter som et CommandArgs-objekt
    """
    parameters = {}

    for arg in args:
        if arg.startswith("/"):
            parameters["startRecording"] = arg == "/startRecording"
        else:
            parts = arg.split("=")
            if len(parts) == 2:
                key, value = parts
                parameters[key] = value

    return CommandArgs(**parameters)


class SimpleRecordingManager:
    """
    Forenklet manager til lydoptagelsesprocesser.
    """

    def __init__(self, args: Dict[str, str], config: BaseConfig):
        """
        Initialisér optagelsesmanager.

        Argumenter:
            args: Kommandolinje-argumenter
            config: Konfiguration baseret på miljø
        """
        self.args = args
        self.config = config
        self.call_id = args["CallID"]
        self.stop_event = threading.Event()
        self.caller_queue = queue.Queue()
        self.agent_queue = queue.Queue()
        self.threads = []
        self.flag_file = os.path.join(
            os.path.expanduser("~"), f"simple-flag-{args['AgentID']}.txt"
        )
        # Lokationen lyden sendes til, standard er openai
        self.loc = "openai"
        # Tilføj en reference til transcriber-instansen hvis brugt
        self.openai_transcriber_instance = None

    def _process_queue_azure(self, data_queue: queue.Queue, speaker: str) -> None:
        """
        Behandl data fra køen og send dem til Azure Blob Storage.

        Argumenter:
            data_queue: Kø med lyddata eller metadata
            speaker: Højttaleridentifikation ('agent' eller 'caller')
        """
        from audio_streamer.azure_storage import AzureStorage

        # Initialisér AzureStorage
        storage = AzureStorage(
            config=self.config,
            speaker=speaker,
            call_id=self.args["CallID"],
            agent_id=self.args["AgentID"],
            queue_id=self.args["Queue"],
            cpr=self.args.get("CPR", ""),
        )

        # Opret metadata for lydsegmenter som placeholder (overskrives med værdier fra data)
        metadata = {
            "sample_width": 2,
            "channels": 1,
            "frame_rate": 44100,
        }

        # Fortsæt så længe stop_event ikke er sat eller der stadig er data i køen
        while not self.stop_event.is_set() or not data_queue.empty():
            try:
                # Udtræk data fra køen med timeout
                data = data_queue.get(timeout=0.1)

                # Hvis data i køen er metadata, opdateres metadata og ellers fortsæt
                if isinstance(data, str):
                    metadata = json.loads(data)
                    continue

                # Hvis data er None, fortsæt til næste iteration
                if data is None:
                    continue

                # Send lyd til audio-container og metadata til queue
                storage.store_segment(data, metadata)

            # Hvis køen er tom, fortsæt til næste iteration
            except queue.Empty:
                continue

            except Exception as e:
                logger.exception(
                    f"Call_id {self.call_id}: Fejl i behandling af data for speaker '{speaker}': {e}"
                )

        logger.debug(
            f"Call_id {self.call_id}: Afslutter storage for speaker '{speaker}' med køstørrelse: {data_queue.qsize()}"
        )

        # Vi venter 3 sekunder for at sikre alt data et kommet ned i køen
        sleep_time = 0.1
        total_sleep_time = 3 / sleep_time
        for i in range(int(total_sleep_time)):
            time.sleep(sleep_time)
            if data_queue.empty():
                continue
            data = data_queue.get(timeout=0.1)
            if data:
                storage.store_segment(data, metadata=metadata)

        # Afslut storage
        storage.finalize()

    def _process_queue_openai(self, queue: queue.Queue, speaker: str) -> None:
        """
        Behandl lyddata fra en enkelt kø (agent eller caller) ved hjælp af Azure OpenAI Transcriber.

        Args:
            queue: Queue med lyddata
            speaker: Højttaleridentifikation ('agent' eller 'caller')
        """
        from audio_streamer.openai_transcriber import AzureOpenAITranscriber

        try:
            logger.info(
                f"Call_id {self.call_id}: Initializing Azure OpenAI Transcriber process for {speaker}."
            )
            # Instantiér transcribereren med den specifikke speaker
            self.openai_transcriber_instances = getattr(
                self, "openai_transcriber_instances", {}
            )
            transcriber = AzureOpenAITranscriber(
                args=self.args,
                config=self.config,
                speaker=speaker,
                controller_version=self.controller_version,
            )
            self.openai_transcriber_instances[speaker] = transcriber

            # Start processeringsløkken som håndterer en enkelt kø
            transcriber.process_queue(queue, self.stop_event)

            logger.info(
                f"Call_id {self.call_id}: Azure OpenAI Transcriber process finished for {speaker}."
            )

        except Exception as e:
            logger.exception(
                f"Call_id {self.call_id}: Error in OpenAI transcription process for {speaker}: {e}"
            )

    def _create_flag_file(self) -> None:
        """
        Opret en flag-fil for at vise, at optagelse er i gang.
        """
        try:
            with open(self.flag_file, "w") as f:
                f.write(str(os.getpid()))
        except Exception as e:
            logger.exception(
                f"Call_id {self.call_id}: Fejl ved oprettelse af flag file: {e}"
            )

    def _remove_flag_file(self) -> None:
        """
        Fjern flag-fil for at vise, at optagelsen er stoppet.
        """
        if os.path.exists(self.flag_file):
            try:
                os.remove(self.flag_file)
                logger.info(
                    f"Call_id {self.call_id}: Flag file '{self.flag_file}' blev fjernet."
                )
            except Exception as e:
                logger.exception(
                    f"Call_id {self.call_id}: Der opstod en fejl med at fjerne flag file: {e}"
                )

    def _start_thread(self, target: callable, args: tuple) -> threading.Thread:
        """
        Start en ny tråd.
        """
        thread = threading.Thread(target=target, args=args)
        thread.daemon = True
        thread.start()
        self.threads.append(thread)
        return thread

    def start(self, icon) -> None:
        """
        Start optagelsesprocessen.
        """
        self.icon = icon
        # Opret flag-fil
        self._create_flag_file()

        # Start optagelsestråde
        caller_recorder = SpeakerRecorder(self.stop_event, self.caller_queue, self.args)
        agent_recorder = MicrophoneRecorder(
            self.stop_event, self.agent_queue, self.args
        )

        self._start_thread(caller_recorder.start, ())
        self._start_thread(agent_recorder.start, ())

        # --- Bestem processeringslokation ---
        try:
            # Hent config fra leverance (on-prem)
            config_location_url = f"{self.config.LEVERANCE_URL}/get_config"
            logger.info(
                f"Call_id {self.call_id}: Fetching config from: {config_location_url}"
            )
            config_location = requests.get(
                config_location_url,
                params={
                    "kr_initialer": self.args["AgentID"],
                    "uid": self.args["CallID"],
                },
                verify=False,
                timeout=10,
            )
            # Rejs en HTTPError ved dårlige svar (4xx eller 5xx)
            config_location.raise_for_status()

            config_data = config_location.json()

            logger.info(f"Call_id {self.call_id}: Received config data: {config_data}")

            miljoe = config_data.get("miljoe", "prod").lower()
            if miljoe not in ["prod", "dev"]:
                logger.warning(
                    f"Call_id {self.call_id}: Invalid environment '{miljoe}' specified in config. Defaulting to 'prod'."
                )
                miljoe = "prod"

            # Tjek konfiguration for streamer og controller
            streamer_version = config_data.get("streamer_version", "openai").lower()
            if streamer_version == "azure":
                self.loc = "azure"
            self.controller_version = config_data.get(
                "controller_version", "onprem"
            ).lower()

            # Opdatér config baseret på hentet miljø
            self.config = get_config(
                env=miljoe, azure=(self.controller_version == "azure")
            )

        except requests.exceptions.RequestException as e:
            logger.warning(
                f"Call_id {self.call_id}: Could not fetch config from {config_location_url}. Error: {e}. Defaulting to '{self.loc}'."
            )
        except json.JSONDecodeError as e:
            logger.warning(
                f"Call_id {self.call_id}: Error decoding JSON response from config endpoint. Error: {e}. Defaulting to '{self.loc}'."
            )
        except Exception as e:
            logger.exception(
                f"Call_id {self.call_id}: An unexpected error occurred during config fetching. Error: {e}. Defaulting to '{self.loc}'."
            )

        logger.info(f"Call_id {self.call_id}: Using '{self.loc}' for processing.")

        # --- Start processeringstråd baseret på lokation ---
        if self.loc == "openai":
            from dotenv import load_dotenv

            # Indlæs miljøvariable for Azure credentials
            load_dotenv(override=True)
            # Start separate OpenAI processeringstråde for agent og caller
            self._start_thread(self._process_queue_openai, (self.agent_queue, "agent"))
            self._start_thread(
                self._process_queue_openai, (self.caller_queue, "caller")
            )
        else:
            # Brug Azure som standard
            # Start storage-tråde for Azure
            self._start_thread(self._process_queue_azure, (self.caller_queue, "caller"))
            self._start_thread(self._process_queue_azure, (self.agent_queue, "agent"))

        # Hold øje med keyboard-afbrydelse eller sletning af flag-fil
        try:
            i = 0
            while os.path.exists(self.flag_file):
                # Vent 1 sekund før notifikation
                if i == 2:
                    icon.notify("Optagelse startet", "Journalnotatsassistenten")
                time.sleep(0.5)
                i += 1

            # Flag-fil blev fjernet eller optagelse stoppet via tray-ikon, udløs stop
            logger.info(
                f"Call_id {self.call_id}: Flag file removed or recording stopped via tray icon, initiating stop sequence."
            )
            self.stop()

        except KeyboardInterrupt:
            logger.info(
                f"Call_id {self.call_id}: Keyboard interrupt received, initiating stop sequence."
            )
            self.stop()
        except Exception as e:
            logger.exception(
                f"Call_id {self.call_id}: Error in main monitoring loop: {e}"
            )
            # Forsøg at stoppe pænt selv ved uventede fejl

            self.stop()

    def stop(self) -> None:
        """
        Stop optagelsesprocessen.
        """
        if self.stop_event.is_set():
            logger.info(f"Call_id {self.call_id}: Stop process already initiated.")
            # Undgå at køre stop-logikken flere gange
            return
        logger.info(f"Call_id {self.call_id}: Stopping recording process...")
        self.icon.notify("Optagelse stoppet", "Journalnotatsassistenten")

        # Fjern flag-fil først for at forhindre genstartsløkker hvis overvåget eksternt
        self._remove_flag_file()

        # Signalér tråde om at stoppe *før* der joines
        logger.info(f"Call_id {self.call_id}: Signaling threads to stop...")
        self.stop_event.set()

        # Vent på at tråde afslutter med timeout
        logger.info(f"Call_id {self.call_id}: Waiting for threads to join...")
        for thread in self.threads:
            thread.join(timeout=30)

            if thread.is_alive():
                logger.warning(
                    f"Call_id {self.call_id}: Thread '{thread.name}' did not finish within timeout."
                )
            else:
                logger.info(
                    f"Call_id {self.call_id}: Thread '{thread.name}' joined successfully."
                )
            # Hold styr på tråde for potentielle senere checks hvis nødvendigt

        # Bemærk: OpenAI-transcriberens finalize-metode kaldes internt,
        # når dens process_queues-løkke afsluttes på grund af at stop_eventet er sat.

        logger.info(f"Call_id {self.call_id}: All threads processed.")

        # Notificér leverance hvis der bruges openai lokation
        if self.loc == "openai":

            def _notify_leverance(call_id: str, url: str) -> None:
                """
                Kalder leverance API når transkribering er færdig.
                """
                try:
                    uid = str(uuid4())

                    response = requests.get(
                        url,
                        params={
                            "call_id": call_id,
                            "uid": uid,
                            "storage_type": "azure",
                        },
                        auth=("jn", os.getenv("LEVERANCE_PASSWORD")),
                        verify=False,
                    )
                    response.raise_for_status()
                    logger.info(
                        f"Notified Leverance at {url} for call-id '{call_id}' with uid {uid}. Status code: {response.status_code}"
                    )
                except Exception as e:
                    logger.error(
                        f"Error calling leverance at {url} for call-id '{call_id}': {e}"
                    )

            # Fire-and-forget notifikationen til leverance for at undgå at blokere hovedtråden
            # Afhængigt af konfiguration kaldes /process_call i controller i web app eller controller on-prem
            threading.Thread(
                target=_notify_leverance,
                args=(
                    self.args["CallID"],
                    self.config.LEVERANCE_URL_PROCESS_CALL,
                ),
            ).start()

        # Tillad et kort øjeblik for endelig oprydning/logning
        time.sleep(1)

        # Stop systembakkeikonet
        try:
            self.icon.stop()
            logger.info(f"Call_id {self.call_id}:System tray icon stopped.")
        except Exception as e:
            logger.exception(
                f"Call_id {self.call_id}: Error stopping system tray icon: {e}"
            )

        logger.info(f"Call_id {self.call_id}: Recording process stopped.")
        # Overvej os._exit(0) hvis en ren afslutning er absolut nødvendig med det samme,
        # men at lade hovedtråden afslutte naturligt er generelt foretrukket.


def main() -> None:
    """
    Main function for den enkle audio-streamer.
    """
    try:
        # Skjul konsolvinduet hvis kører som eksekverbar
        if getattr(sys, "frozen", False):
            hide_console_window()

        # Log de rå argumenter fra Genesys
        logger.info(f"Genesys sys.argv for audio streamer: {sys.argv}")

        # Parsér kommandolinje-argumenter
        cli_args = parse_args(sys.argv[1:])
        args_dict = cli_args.model_dump()

        # Fjern CPR fra logging
        args_log = args_dict.copy()
        args_log.pop("CPR", None)
        logger.info(f"Audiostreamer blev kaldt med følgende argumenter: {args_log}")

        # Undlad at starte audiostreamer hvis AgentID fra Genesys er en tom streng
        if not args_dict["AgentID"]:
            logger.warning(
                f"Call_id {args_dict['CallID']}: Intet AgentID fundet fra Genesys. Exiting."
            )
            return

        # Gør agent ID til store bogstaver og gør CallID unikt
        args_dict["AgentID"] = args_dict["AgentID"].upper()
        args_dict["CallID"] = f"{args_dict['CallID']}-{args_dict['AgentID']}"

        # Tjek om der skal køres mod Azure for controller
        use_azure = args_dict.get("controller_version", "onprem").lower() == "azure"

        # Hent konfiguration for specificeret miljø
        config = get_config(env=args_dict.get("ENV", "prod"), azure=use_azure)
        logger.info(f"Konfiguration: {config}")

        # Opret optagelsesmanager
        manager = SimpleRecordingManager(args_dict, config)

        if args_dict["startRecording"]:
            # Opret systembakkeikon i en separat tråd
            icon = TrayIcon(exit_callback=exit_app)
            manager.start(icon)
        else:
            # Stop optagelse
            manager._remove_flag_file()

    except KeyboardInterrupt:
        manager.stop()

    except Exception as e:
        logger.exception(f"Der opstod en fejl i audiostreameren: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
