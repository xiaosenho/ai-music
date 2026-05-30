#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOOT_SCRIPT="${SCRIPT_DIR}/start-worker.sh"
LINE="@reboot /usr/bin/env bash '${BOOT_SCRIPT}' tmux"

if ! command -v crontab >/dev/null 2>&1; then
  echo "[install-autostart] crontab not found on this image" >&2
  exit 1
fi

CURRENT_CRON="$(mktemp)"
trap 'rm -f "${CURRENT_CRON}"' EXIT

crontab -l 2>/dev/null > "${CURRENT_CRON}" || true

if grep -Fq "${BOOT_SCRIPT}" "${CURRENT_CRON}"; then
  echo "[install-autostart] autostart already installed"
  exit 0
fi

printf "\n%s\n" "${LINE}" >> "${CURRENT_CRON}"
crontab "${CURRENT_CRON}"

echo "[install-autostart] installed crontab entry:"
echo "${LINE}"
