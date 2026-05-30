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

if command -v tmux >/dev/null 2>&1 && tmux has-session -t "${SESSION_NAME}" 2>/dev/null; then
  tmux kill-session -t "${SESSION_NAME}"
  echo "[stop-worker] tmux session stopped: ${SESSION_NAME}"
fi

pkill -f "worker.py" >/dev/null 2>&1 || true
echo "[stop-worker] worker processes stopped"
