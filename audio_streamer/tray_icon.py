import os
import sys
import threading

# Tilføj imports til systembakkeikon
import pystray
import sounddevice as sd
import urllib3
from loguru import logger
from PIL import Image

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class TrayIcon:
    def __init__(self, exit_callback=None):
        # Optagelsesstatus
        self.is_recording = False
        self.recording_thread = None

        # Optagelsesparametre
        self.sample_rate = 44100
        self.channels = 2
        self.device = None

        # Hent den korrekte sti til ikon filen
        if getattr(sys, "frozen", False):
            # Kører som kompileret eksekverbar fil
            application_path = os.path.dirname(sys.executable)
            self.image_path = os.path.join(application_path, "jnlogo.png")
        else:
            # Kører som et normalt Python script
            self.image_path = "jnlogo.png"

        # Hent liste over inputenheder
        self.input_devices = [
            device for device in sd.query_devices() if device["max_input_channels"] > 0
        ]

        self.menu_title = "Journalnotatsassistenten"
        self.microphone = None
        self.speaker = None
        self.exit_callback = exit_callback

        # Opret systembakkeikon
        self.icon = self.create_tray_icon()
        self.icon_thread = threading.Thread(target=self.icon.run)
        self.icon_thread.daemon = True
        self.icon_thread.start()
        logger.info("Tray icon started.")

    def _set_speaker(self, device):
        """
        Indstil højttalerenheden
        """
        self.speaker = device

    def _set_microphone(self, device):
        """
        Indstil mikrofonenheden
        """
        self.microphone = device

    def _create_icon_image(self, active=True):
        """
        Opretter et ikonbillede til Windows' systembakke.
        Grøn cirkel når der optages, grå cirkel når der ikke optages.
        """
        width = 64
        height = 64

        # Opret et gennemsigtigt billede
        image = Image.open(self.image_path).convert("RGBA")
        image = image.resize((width, height))

        # Konverter grøn til grå hvis ikke optages
        if not active:
            image = image.convert("L")
            image = image.convert("RGBA")
        return image

    def _log_devices(self):
        """
        Logger en liste af default enheder fra SoundDevice
        """
        for device in sd.default.device:
            logger.info(f"Default device: {device}")

    def create_tray_icon(self):
        """
        Opret systembakkeikon med menu
        """

        # Hovedmenu
        menu = (
            pystray.MenuItem("Log lyd enheder", lambda: self._log_devices()),
            pystray.MenuItem("Exit", lambda: self.exit_callback() if self.exit_callback else None),
        )

        icon = pystray.Icon(
            "Journalnotatsassistenten",
            self._create_icon_image(True),
            self.menu_title,
            menu,
        )

        return icon

    def notify(self, title: str, message: str):
        """
        Viser en notifikation i systembakken
        """
        self.icon.notify(title, message)
        logger.info(f"Notification: {title} - {message}")

    def stop(self):
        """
        Stop systembakkeikon
        """
        self.icon.stop()
        logger.info("Tray icon stopped.")
