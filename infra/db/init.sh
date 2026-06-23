#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MSSQL_HOST="${MSSQL_HOST:-mssql}"
MSSQL_PORT="${MSSQL_PORT:-1433}"
MSSQL_SA_USER="${MSSQL_SA_USER:-sa}"
MSSQL_SA_PASSWORD="${MSSQL_SA_PASSWORD:-}"
LEVERANCE_BUSINESS_DATABASE_NAME="${LEVERANCE_BUSINESS_DATABASE_NAME:-leverance}"
MSSQL_WAIT_TIMEOUT="${MSSQL_WAIT_TIMEOUT:-120}"
MSSQL_WAIT_INTERVAL="${MSSQL_WAIT_INTERVAL:-2}"

if ! command -v sqlcmd >/dev/null 2>&1; then
  echo "sqlcmd not found in PATH" >&2
  exit 1
fi

if [[ -z "${MSSQL_SA_PASSWORD}" ]]; then
  echo "MSSQL_SA_PASSWORD must be set" >&2
  exit 1
fi

SQLCMD_BASE=(
  sqlcmd
  -C
  -I
  -S "${MSSQL_HOST},${MSSQL_PORT}"
  -U "${MSSQL_SA_USER}"
  -P "${MSSQL_SA_PASSWORD}"
  -b
)

echo "Waiting for SQL Server at ${MSSQL_HOST}:${MSSQL_PORT} ..."
start_ts="$(date +%s)"
while true; do
  if "${SQLCMD_BASE[@]}" -d master -Q "SELECT 1" >/dev/null 2>&1; then
    break
  fi

  now_ts="$(date +%s)"
  if (( now_ts - start_ts >= MSSQL_WAIT_TIMEOUT )); then
    echo "Timed out waiting for SQL Server after ${MSSQL_WAIT_TIMEOUT}s" >&2
    exit 1
  fi

  sleep "${MSSQL_WAIT_INTERVAL}"
done

echo "SQL Server is ready. Applying database scripts..."
for script in \
  "${SCRIPT_DIR}/01_create_database.sql" \
  "${SCRIPT_DIR}/02_schema.sql" \
  "${SCRIPT_DIR}/03_seed.sql"; do
  echo "Running $(basename "${script}")"
  "${SQLCMD_BASE[@]}" \
    -d master \
    -i "${script}" \
    -v DatabaseName="${LEVERANCE_BUSINESS_DATABASE_NAME}"
done

echo "Database initialization completed for ${LEVERANCE_BUSINESS_DATABASE_NAME}."
