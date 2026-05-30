#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKER_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${AIMUSIC_WORKER_ENV_FILE:-${WORKER_DIR}/.env}"
SESSION_NAME="${AIMUSIC_WORKER_TMUX_SESSION:-aimusic-worker}"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  source "${ENV_FILE}"
  set +a
  SESSION_NAME="${AIMUSIC_WORKER_TMUX_SESSION:-${SESSION_NAME}}"
fi

echo "Worker dir: ${WORKER_DIR}"
echo "Env file : ${ENV_FILE}"
echo

if command -v tmux >/dev/null 2>&1 && tmux has-session -t "${SESSION_NAME}" 2>/dev/null; then
  echo "tmux: running (${SESSION_NAME})"
else
  echo "tmux: not running"
fi

echo
echo "Processes:"
pgrep -af "worker.py" || echo "none"

echo
if [[ -f "${WORKER_DIR}/logs/worker.log" ]]; then
  echo "Recent logs:"
  tail -n 30 "${WORKER_DIR}/logs/worker.log"
else
  echo "No worker log file yet."
fi
