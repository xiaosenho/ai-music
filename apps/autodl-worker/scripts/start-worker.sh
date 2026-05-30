#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKER_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${AIMUSIC_WORKER_ENV_FILE:-${WORKER_DIR}/.env}"
PYTHON_BIN="${AIMUSIC_WORKER_PYTHON_BIN:-}"
SESSION_NAME="${AIMUSIC_WORKER_TMUX_SESSION:-aimusic-worker}"
MODE="${1:-tmux}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[start-worker] missing env file: ${ENV_FILE}" >&2
  exit 1
fi

set -a
source "${ENV_FILE}"
set +a

if [[ -z "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="${AIMUSIC_RVC_PYTHON_BIN:-python3}"
fi

mkdir -p "${WORKER_DIR}/logs" "${WORKER_DIR}/runs" "${WORKER_DIR}/.state"

cd "${WORKER_DIR}"

if [[ "${AIMUSIC_WORKER_AUTO_GIT_PULL:-false}" == "true" ]] && command -v git >/dev/null 2>&1; then
  git pull --ff-only || true
fi

start_foreground() {
  exec "${PYTHON_BIN}" worker.py
}

start_tmux() {
  if ! command -v tmux >/dev/null 2>&1; then
    echo "[start-worker] tmux not found, falling back to nohup" >&2
    start_nohup
    return
  fi

  if tmux has-session -t "${SESSION_NAME}" 2>/dev/null; then
    echo "[start-worker] tmux session already exists: ${SESSION_NAME}"
    exit 0
  fi

  tmux new-session -d -s "${SESSION_NAME}" \
    "cd '${WORKER_DIR}' && set -a && source '${ENV_FILE}' && set +a && '${PYTHON_BIN}' worker.py >> '${WORKER_DIR}/logs/worker.log' 2>&1"
  echo "[start-worker] worker started in tmux session: ${SESSION_NAME}"
}

start_nohup() {
  if pgrep -f "${PYTHON_BIN} worker.py" >/dev/null 2>&1; then
    echo "[start-worker] worker process already running"
    exit 0
  fi

  nohup "${PYTHON_BIN}" worker.py >> "${WORKER_DIR}/logs/worker.log" 2>&1 &
  echo "[start-worker] worker started with nohup"
}

case "${MODE}" in
  foreground)
    start_foreground
    ;;
  tmux)
    start_tmux
    ;;
  nohup)
    start_nohup
    ;;
  *)
    echo "Usage: $0 [foreground|tmux|nohup]" >&2
    exit 1
    ;;
esac
