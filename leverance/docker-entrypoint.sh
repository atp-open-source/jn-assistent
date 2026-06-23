#!/usr/bin/env bash
# Entrypoint for the dockerised Leverance backend.
#
# Når stacken kører lokalt mod Azurite (JN_LOCAL_MODE=1 + emulator-
# connection string "UseDevelopmentStorage=true"), forventer Azure SDK'et
# at storage-emulatoren findes på 127.0.0.1:10000-10002. 
#
# Azurites shared-key-validering accepterer KUN den signaturform som SDK'et bruger i
# emulator-mode (mod 127.0.0.1) — en eksplicit connection string mod et
# hostnavn fejler med AuthorizationFailure. Derfor videresender vi
# 127.0.0.1:1000x -> ${AZURITE_HOST}:1000x med socat, så emulator-mode
# virker uændret inde i containeren.

set -euo pipefail

AZURITE_HOST="${AZURITE_HOST:-azurite}"
conn="${AZURE_STORAGE_CONNECTION_STRING:-}"

start_forward() {
    local listen_port="$1"
    local target_host="$2"
    local target_port="$3"
    socat "TCP4-LISTEN:${listen_port},fork,reuseaddr,bind=127.0.0.1" \
        "TCP4:${target_host}:${target_port}" &
}

# Aktivér kun forwarders i emulator/lokal-mode.
if [[ "${JN_LOCAL_MODE:-}" == "1" && "${conn,,}" == *"usedevelopmentstorage=true"* ]]; then
    if command -v socat >/dev/null 2>&1; then
        echo "[entrypoint] Videresender 127.0.0.1:10000-10002 -> ${AZURITE_HOST}:10000-10002 (Azurite emulator-mode)"
        start_forward 10000 "${AZURITE_HOST}" 10000
        start_forward 10001 "${AZURITE_HOST}" 10001
        start_forward 10002 "${AZURITE_HOST}" 10002
        # Kort pause så lytterne er klar inden appen starter.
        sleep 1
    else
        echo "[entrypoint] ADVARSEL: socat mangler — kan ikke videresende til Azurite" >&2
    fi
fi

exec "$@"
