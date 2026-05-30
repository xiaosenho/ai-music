#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKER_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${AIMUSIC_WORKER_ENV_FILE:-${WORKER_DIR}/.env}"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  source "${ENV_FILE}"
  set +a
fi

PYTHON_BIN="${AIMUSIC_RVC_PYTHON_BIN:-/root/miniconda3/bin/python}"
RVC_ROOT_DIR="${AIMUSIC_RVC_ROOT_DIR:-/Retrieval-based-Voice-Conversion-WebUI}"
INSTALL_TMUX="${AIMUSIC_INSTALL_TMUX:-false}"
FULL_RVC_DEPS="${AIMUSIC_INSTALL_FULL_RVC_DEPS:-false}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "[install-deps] python not found or not executable: ${PYTHON_BIN}" >&2
  exit 1
fi

echo "[install-deps] worker dir : ${WORKER_DIR}"
echo "[install-deps] env file   : ${ENV_FILE}"
echo "[install-deps] python     : ${PYTHON_BIN}"
echo "[install-deps] rvc root   : ${RVC_ROOT_DIR}"

install_with_apt() {
  local package="$1"
  if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y "${package}"
  else
    echo "[install-deps] apt-get is not available, please install ${package} manually" >&2
    return 1
  fi
}

ensure_command() {
  local command_name="$1"
  local apt_package="$2"
  if command -v "${command_name}" >/dev/null 2>&1; then
    echo "[install-deps] found command: ${command_name}"
    return 0
  fi
  echo "[install-deps] missing command: ${command_name}, installing ${apt_package}"
  install_with_apt "${apt_package}"
}

ensure_python_module() {
  local module_name="$1"
  if "${PYTHON_BIN}" - <<PY >/dev/null 2>&1
import ${module_name}
PY
  then
    echo "[install-deps] found python module: ${module_name}"
    return 0
  fi
  return 1
}

echo "[install-deps] pinning pip to a legacy-compatible version for RVC dependencies"
"${PYTHON_BIN}" -m pip install -U "pip<24.1" setuptools wheel

ensure_command ffmpeg ffmpeg
ensure_command ffprobe ffmpeg

if [[ "${INSTALL_TMUX}" == "true" ]]; then
  ensure_command tmux tmux
fi

echo "[install-deps] installing worker runtime packages"
"${PYTHON_BIN}" -m pip install soundfile
"${PYTHON_BIN}" -m pip install -U git+https://github.com/facebookresearch/demucs#egg=demucs

if [[ "${FULL_RVC_DEPS}" == "true" ]]; then
  if [[ -f "${RVC_ROOT_DIR}/requirements.txt" ]]; then
    echo "[install-deps] installing full RVC requirements from ${RVC_ROOT_DIR}/requirements.txt"
    "${PYTHON_BIN}" -m pip install -r "${RVC_ROOT_DIR}/requirements.txt"
  else
    echo "[install-deps] requirements.txt not found under ${RVC_ROOT_DIR}, skipping full install" >&2
  fi
fi

echo "[install-deps] verifying key python modules"

missing_modules=()
for module_name in torch soundfile demucs; do
  if ! ensure_python_module "${module_name}"; then
    missing_modules+=("${module_name}")
  fi
done

optional_modules=(faiss fairseq)
for module_name in "${optional_modules[@]}"; do
  if ensure_python_module "${module_name}"; then
    :
  else
    echo "[install-deps] optional module missing: ${module_name}" >&2
    missing_modules+=("${module_name}")
  fi
done

if [[ ${#missing_modules[@]} -gt 0 ]]; then
  echo "[install-deps] some modules are still missing: ${missing_modules[*]}" >&2
  echo "[install-deps] if faiss/fairseq are missing, your RVC image may be incomplete; consider setting AIMUSIC_INSTALL_FULL_RVC_DEPS=true and rerunning." >&2
  exit 1
fi

echo
echo "[install-deps] all required dependencies look ready"
echo "[install-deps] next steps:"
echo "  cd ${WORKER_DIR}"
echo "  bash ./scripts/start-worker.sh nohup"
