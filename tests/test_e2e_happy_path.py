from __future__ import annotations

import contextlib
import json
import os
import time
from uuid import uuid4

import pytest
import requests
from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import ContainerClient

pytestmark = pytest.mark.skipif(
    not os.getenv("JN_E2E_BASE_URL") or not os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
    reason="JN_E2E_BASE_URL and AZURE_STORAGE_CONNECTION_STRING are required for live E2E",
)


def _upload_jsonl_blob(container: ContainerClient, blob_name: str, rows: list[dict]) -> None:
    payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    container.upload_blob(name=blob_name, data=payload.encode("utf-8"), overwrite=True)


def test_process_call_happy_path_against_live_stack():
    base_url = os.environ["JN_E2E_BASE_URL"].rstrip("/")
    connection_string = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    call_id = f"pytest-{uuid4()}"
    agent_id = "TEST"
    queue_id = "TEST-KOE"
    cpr = "0101011234"

    container = ContainerClient.from_connection_string(
        conn_str=connection_string,
        container_name="transcriptions",
    )
    with contextlib.suppress(ResourceExistsError):
        container.create_container()

    agent_rows = [
        {
            "status": "start",
            "call_id": call_id,
            "agent_id": agent_id,
            "koe_id": queue_id,
            "cpr": cpr,
            "time": "2026-01-01T12:00:00.000000Z",
        },
        {
            "type": "transcript",
            "call_id": call_id,
            "agent_id": agent_id,
            "speaker": "agent",
            "timestamp": "1.0",
            "time": "2026-01-01T12:00:01.000000Z",
            "sentence": "Borger ønsker status på sin sag.",
            "queue_id": queue_id,
            "cpr": cpr,
        },
        {
            "status": "end",
            "call_id": call_id,
            "agent_id": agent_id,
            "koe_id": queue_id,
            "cpr": cpr,
            "time": "2026-01-01T12:00:02.000000Z",
        },
    ]
    caller_rows = [
        {
            "status": "start",
            "call_id": call_id,
            "agent_id": agent_id,
            "koe_id": queue_id,
            "cpr": cpr,
            "time": "2026-01-01T12:00:00.000000Z",
        },
        {
            "type": "transcript",
            "call_id": call_id,
            "agent_id": agent_id,
            "speaker": "caller",
            "timestamp": "2.0",
            "time": "2026-01-01T12:00:02.000000Z",
            "sentence": "Tak for hjælpen.",
            "queue_id": queue_id,
            "cpr": cpr,
        },
        {
            "status": "end",
            "call_id": call_id,
            "agent_id": agent_id,
            "koe_id": queue_id,
            "cpr": cpr,
            "time": "2026-01-01T12:00:03.000000Z",
        },
    ]

    _upload_jsonl_blob(container, f"transcriptions-{call_id}-agent.jsonl", agent_rows)
    _upload_jsonl_blob(container, f"transcriptions-{call_id}-caller.jsonl", caller_rows)

    process_response = requests.get(
        f"{base_url}/api/jn/process_call",
        params={"call_id": call_id},
        timeout=15,
    )
    assert process_response.status_code == 200, process_response.text

    deadline = time.time() + 15
    last_status_payload = None
    while time.time() < deadline:
        status_response = requests.get(
            f"{base_url}/api/jn/fetch_status",
            params={"kr_initialer": agent_id},
            timeout=10,
        )
        assert status_response.status_code == 200, status_response.text
        last_status_payload = status_response.json()
        if last_status_payload.get("Status") == "end-summary":
            break
        time.sleep(1)

    assert last_status_payload is not None
    assert last_status_payload.get("Status") == "end-summary"

    notat_response = requests.get(
        f"{base_url}/api/jn/get_notat",
        params={"kr_initialer": agent_id, "call_id": call_id},
        timeout=10,
    )
    assert notat_response.status_code == 200, notat_response.text
    payload = notat_response.json()
    assert payload["call_id"] == call_id
    assert payload["notat"].strip()
