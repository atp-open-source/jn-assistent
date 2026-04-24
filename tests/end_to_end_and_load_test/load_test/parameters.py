import datetime as dt
import os

import locust.stats
from dotenv import load_dotenv

load_dotenv(override=True)

# Miljø for kørsel af load testen (dev, prod, etc.)
ENV = os.getenv("ENV", "dev").lower()
CONTROLLER_VERSION = os.getenv("CONTROLLER_VERSION", "azure").lower()

# Timestamp for kørsel af load testen
TIMESTAMP = os.getenv("TIMESTAMP", dt.datetime.now().strftime("%y%m%d_%H%M%S"))

# Antal workers/processer der kører load testen, for at fordele CPU load.
# Eksperimentelt - bør kun være nødvendigt at sætte højere end 1 hvis man får
# advarslen "WARNING/root: CPU usage above 90%! ..."
NUM_WORKERS = int(os.getenv("NUM_WORKERS", "1"))

# Ventetid mellem opkald i sekunder
MIN_WAIT_TIME = int(os.getenv("MIN_WAIT_TIME", "300"))
MAX_WAIT_TIME = int(os.getenv("MAX_WAIT_TIME", "600"))

# Varighed af opkald i sekunder
CALL_DURATION_RANGES = {
    "short": (
        int(os.getenv("MIN_SHORT_CALL_DURATION", "30")),
        int(os.getenv("MAX_SHORT_CALL_DURATION", "180")),
    ),
    "medium": (
        int(os.getenv("MIN_MEDIUM_CALL_DURATION", "180")),
        int(os.getenv("MAX_MEDIUM_CALL_DURATION", "360")),
    ),
    "long": (
        int(os.getenv("MIN_LONG_CALL_DURATION", "360")),
        int(os.getenv("MAX_LONG_CALL_DURATION", "600")),
    ),
}

# Vægtning af korte, mellem og lange opkald
CALL_DURATION_WEIGHTS = {
    "short": float(os.getenv("CALL_DURATION_WEIGHT_SHORT", "50")),
    "medium": float(os.getenv("CALL_DURATION_WEIGHT_MEDIUM", "30")),
    "long": float(os.getenv("CALL_DURATION_WEIGHT_LONG", "20")),
}

# Mock transskribering og process_call kald (for at spare på tokens under debugging)
MOCK_TRANSCRIPTION = os.getenv("MOCK_TRANSCRIPTION", "true").lower() == "true"
MOCK_PROCESS_CALL = os.getenv("MOCK_PROCESS_CALL", "true").lower() == "true"

# Sti til output CSV-fil for aktive opkaldsdata
ACTIVE_CALLS_OUTPUT_PATH = os.getenv(
    "ACTIVE_CALLS_OUTPUT_PATH", f"output/loadtest_{TIMESTAMP}_active_calls_history.csv"
)

# Konfiguration for hvor ofte Locust skal gemme statistikker
locust.stats.CSV_STATS_INTERVAL_SEC = int(os.getenv("CSV_STATS_INTERVAL_SEC", "5"))
locust.stats.CONSOLE_STATS_INTERVAL_SEC = locust.stats.CSV_STATS_INTERVAL_SEC

# Konfiguration for hvor stort et vindue (i sekunder) der skal bruges til beregning af
# rullende percentiler i CSV statistikkerne.
locust.stats.CURRENT_RESPONSE_TIME_PERCENTILE_WINDOW = int(os.getenv("CSV_STATS_WINDOW_SEC", "60"))
