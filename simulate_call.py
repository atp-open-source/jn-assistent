"""Simulér et opkald mod den dockeriserede JN-stack.

Efterligner det FULDE audio_streamer-forløb, så frontenden opdaterer sig selv
live (uden genindlæsning):

  1. Sender 'start-call' til status-køen   -> frontend viser "Lytter til opkald"
  2. Simulerer transkription (sleep)        -> blobs lægges i Azurite
  3. Sender 'end-call' til status-køen      -> frontend skifter til hurtig
                                               polling (hvert 2. sek.)
  4. Kalder /process_call                   -> backend genererer notat og sender
                                               'end-summary' til køen
  5. Frontend henter notatet inden for ~2 sek.

Bagefter ses notatet i frontenden på http://localhost:4173/?username=<AGENT>.

Brug:
    python simulate_call.py [CALL_ID] [AGENT]
    python simulate_call.py --call-id demo-001 --agent TEST

Kræver pakkerne fra .venv (azure-storage-blob, requests):
    source .venv/bin/activate
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from datetime import datetime

import requests
from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import ContainerClient
from azure.storage.queue import QueueServiceClient

# Emulator-mode: Azure SDK'et signerer mod 127.0.0.1:10000-10002, som compose
# publicerer på hosten. (Samme grund som leverance/docker-entrypoint.sh.)
CONNECTION_STRING = "UseDevelopmentStorage=true"
CONTAINER_NAME = "transcriptions"
DEFAULT_BACKEND = "http://localhost:8000"
DEFAULT_FRONTEND = "http://localhost:4173"

# Realistiske ventetider (sekunder).
SLEEP_TRANSCRIPTION = 4  # transkription af et kort opkald
# Efter 'end-call' venter vi lidt over frontendens langsomme poll-interval (10 sek.),
# så frontenden NÅR at se 'end-call', skifter til hurtig polling (hvert 2. sek.) og
# viser "Genererer notat...". Derefter fanges 'end-summary' inden for ~2 sek. Sæt evt.
# til 0 for et hurtigt (men mindre "live") forløb.
SLEEP_AFTER_END_CALL = 11
SLEEP_BEFORE_STATUS = 2  # backend skal nå at skrive notat + sende 'end-summary'


def _ts() -> str:
    """Returner aktuel tid som HH:MM:SS."""
    return datetime.now().strftime("%H:%M:%S")


def _status_row(call_id: str, agent: str, queue: str, cpr: str, status: str) -> dict:
    return {
        "status": status,
        "call_id": call_id,
        "agent_id": agent,
        "koe_id": queue,
        "cpr": cpr,
        "time": "2026-01-01T12:00:00.000000Z",
    }


def _line(
    call_id: str, agent: str, queue: str, cpr: str, speaker: str, ts: str, sentence: str
) -> dict:
    return {
        "type": "transcript",
        "call_id": call_id,
        "agent_id": agent,
        "speaker": speaker,
        "timestamp": ts,
        "sentence": sentence,
        "queue_id": queue,
        "cpr": cpr,
        "time": "2026-01-01T12:00:%02dZ" % int(float(ts)),
    }


def send_status(agent: str, call_id: str, status: str) -> None:
    """Send en statusbesked til status-køen, præcis som audio_streameren gør.

    Køen hedder ``status-<agent>`` (små bogstaver) og beskeden er JSON med
    nøglerne ``call_id``, ``status`` og ``timestamp`` — samme format som
    backendens ``azure_notify_status``.
    """
    queue_name = f"status-{agent.lower()}"
    queue_client = QueueServiceClient.from_connection_string(CONNECTION_STRING).get_queue_client(
        queue_name
    )
    with contextlib.suppress(ResourceExistsError):
        queue_client.create_queue()

    message = {"call_id": call_id, "status": status, "timestamp": time.time()}
    queue_client.send_message(json.dumps(message))
    print(f"[{_ts()}]   ✓ status '{status}' sendt til kø {queue_name}")


def upload_transcriptions(call_id: str, agent: str, queue: str, cpr: str) -> None:
    """Læg agent- og caller-transcriptions i Azurite."""
    agent_rows = [
        _status_row(call_id, agent, queue, cpr, "start"),
        _line(
            call_id,
            agent,
            queue,
            cpr,
            "agent",
            "1.0",
            "Velkommen til kommunen, hvad kan jeg hjælpe med?",
        ),
        _line(
            call_id,
            agent,
            queue,
            cpr,
            "agent",
            "3.0",
            "Jeg kan se din sag og giver dig en status nu.",
        ),
        _status_row(call_id, agent, queue, cpr, "end"),
    ]
    caller_rows = [
        _status_row(call_id, agent, queue, cpr, "start"),
        _line(
            call_id,
            agent,
            queue,
            cpr,
            "caller",
            "2.0",
            "Hej, jeg ringer for at høre status på min sag.",
        ),
        _line(call_id, agent, queue, cpr, "caller", "4.0", "Tak, det lyder fint."),
        _status_row(call_id, agent, queue, cpr, "end"),
    ]

    container = ContainerClient.from_connection_string(CONNECTION_STRING, CONTAINER_NAME)
    with contextlib.suppress(ResourceExistsError):
        container.create_container()

    for speaker, rows in (("agent", agent_rows), ("caller", caller_rows)):
        blob = f"transcriptions-{call_id}-{speaker}.jsonl"
        data = "\n".join(json.dumps(r) for r in rows).encode()
        container.upload_blob(blob, data, overwrite=True)
        print(f"[{_ts()}]   ✓ {blob} uploadet til Azurite")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "call_id",
        nargs="?",
        default=f"demo-{int(time.time())}",
        help="Opkalds-ID (default: demo-<timestamp>)",
    )
    parser.add_argument(
        "agent",
        nargs="?",
        default="TEST",
        help="Agent-initialer; skal matche en seedet jn.config-agent (default: TEST)",
    )
    parser.add_argument("--call-id", dest="call_id_opt", help="Alternativ til positional CALL_ID")
    parser.add_argument("--agent", dest="agent_opt", help="Alternativ til positional AGENT")
    parser.add_argument("--queue", default="DEMO-KOE", help="Kø-ID (default: DEMO-KOE)")
    parser.add_argument("--cpr", default="0101011234", help="CPR (default: 0101011234)")
    parser.add_argument(
        "--backend",
        default=DEFAULT_BACKEND,
        help=f"Leverance-backend (default: {DEFAULT_BACKEND})",
    )
    parser.add_argument(
        "--frontend",
        default=DEFAULT_FRONTEND,
        help=f"Frontend-URL til udskrift (default: {DEFAULT_FRONTEND})",
    )
    args = parser.parse_args(argv)

    call_id = args.call_id_opt or args.call_id
    agent = args.agent_opt or args.agent

    print(f"[{_ts()}] 📋 Starter simulering af opkald")
    print(f"[{_ts()}]    Call ID: {call_id}")
    print(f"[{_ts()}]    Agent:   {agent}")
    print()
    print("💡 Åbn frontenden NU, så kan du se den opdatere sig live:")
    print(f"   {args.frontend}/?username={agent}")
    print()

    try:
        # 1) Opkald starter -> frontend viser "Lytter til opkald..."
        print(f"[{_ts()}] 📞 Opkald startet")
        send_status(agent, call_id, "start-call")

        # 2) Transkription (real audio_streamer transkriberer i real-time)
        print(f"[{_ts()}] 🎙️  Optager og transkriberer ({SLEEP_TRANSCRIPTION} sek.) ...")
        time.sleep(SLEEP_TRANSCRIPTION)
        upload_transcriptions(call_id, agent, args.queue, args.cpr)

        # 3) Opkald slutter -> frontend skifter til hurtig polling (hvert 2. sek.)
        print(f"[{_ts()}] 📴 Opkald afsluttet")
        send_status(agent, call_id, "end-call")
        if SLEEP_AFTER_END_CALL:
            print(
                f"[{_ts()}] ⏳ Venter {SLEEP_AFTER_END_CALL} sek. så frontenden "
                f"opdager 'end-call' og viser \"Genererer notat...\" ..."
            )
            time.sleep(SLEEP_AFTER_END_CALL)
    except Exception as exc:
        print(f"[{_ts()}] ❌ FEJL ved Azurite/kø: {exc}", file=sys.stderr)
        return 1

    # 4) Generér notatet (backend sender 'end-summary' til køen)
    print(f"[{_ts()}] 🔄 Kalder /process_call (generering + validering) ...")
    try:
        resp = requests.get(
            f"{args.backend}/api/jn/process_call",
            params={"call_id": call_id},
            timeout=120,
        )
        if resp.status_code == 200:
            print(f"[{_ts()}]   ✓ {resp.text.strip()}")
        else:
            print(f"[{_ts()}]   ⚠️  Uventet HTTP {resp.status_code}: {resp.text.strip()}")
            return 1
    except requests.RequestException as exc:
        print(
            f"[{_ts()}] ❌ FEJL: kunne ikke nå backenden på {args.backend}: {exc}",
            file=sys.stderr,
        )
        return 1

    # 5) Bekræft status (frontenden henter selv notatet via sin polling)
    print(f"[{_ts()}] ⏳ Venter {SLEEP_BEFORE_STATUS} sek. mens backend forbereder status ...")
    time.sleep(SLEEP_BEFORE_STATUS)
    print(f"[{_ts()}] 🔍 Henter status ...")
    try:
        status = requests.get(
            f"{args.backend}/api/jn/fetch_status",
            params={"kr_initialer": agent},
            timeout=30,
        )
        if status.status_code == 200:
            status_value = status.json().get("Status", "unknown")
            print(f"[{_ts()}]   ✓ Status: {status_value}")
            if status_value == "end-summary":
                print(f"[{_ts()}]   ✓ Notat er klar — frontenden henter det automatisk!")
        else:
            print(f"[{_ts()}]   ⚠️  Uventet HTTP {status.status_code}")
    except requests.RequestException as exc:
        print(f"[{_ts()}] ⚠️  Kunne ikke hente status: {exc}", file=sys.stderr)

    print()
    print(f"[{_ts()}] ✅ Simulering færdig")
    print()
    print("📱 Hvis siden allerede er åben, opdaterer den sig selv inden for ~2 sek.")
    print(f"   Ellers åbn:  {args.frontend}/?username={agent}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
