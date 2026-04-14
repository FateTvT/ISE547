#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-restart}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVICE_NAME="${SERVICE_NAME:-ise547-backend}"
APP_DIR="${APP_DIR:-${PROJECT_ROOT}/backend}"
SUPERVISOR_CONF_DIR="${SUPERVISOR_CONF_DIR:-/etc/supervisor/conf.d}"
TEMPLATE_PATH="${PROJECT_ROOT}/ops/backend.conf"
GENERATED_CONF_PATH="${PROJECT_ROOT}/ops/${SERVICE_NAME}.conf"
TARGET_CONF_PATH="${SUPERVISOR_CONF_DIR}/${SERVICE_NAME}.conf"
if [ -n "${RUN_USER:-}" ]; then
  RUN_USER="${RUN_USER}"
elif [ "$(id -u)" -eq 0 ] && [ -n "${SUDO_USER:-}" ]; then
  RUN_USER="${SUDO_USER}"
else
  RUN_USER="$(id -un)"
fi
RUN_HOME="$(getent passwd "${RUN_USER}" | cut -d: -f6 || true)"
COMMAND="${COMMAND:-}"
BACKEND_PORT="${BACKEND_PORT:-8024}"

usage() {
  echo "Usage: $0 [start|restart|stop|status|deploy]"
}

escape_sed_replacement() {
  printf '%s' "$1" | sed -e 's/[\/&|]/\\&/g'
}

run_with_privilege() {
  if [ -n "${SUDO_CMD}" ]; then
    "${SUDO_CMD}" "$@"
  else
    "$@"
  fi
}

run_as_target_user() {
  if [ "$(id -un)" = "${RUN_USER}" ]; then
    "$@"
    return
  fi

  if command -v sudo >/dev/null 2>&1; then
    sudo -u "${RUN_USER}" "$@"
    return
  fi

  return 1
}

if [ ! -f "${TEMPLATE_PATH}" ]; then
  echo "Template not found: ${TEMPLATE_PATH}" >&2
  exit 1
fi

if [ ! -d "${APP_DIR}" ]; then
  echo "App directory not found: ${APP_DIR}" >&2
  exit 1
fi

if [ ! -d "${SUPERVISOR_CONF_DIR}" ]; then
  echo "Supervisor conf dir not found: ${SUPERVISOR_CONF_DIR}" >&2
  exit 1
fi

if ! command -v supervisorctl >/dev/null 2>&1; then
  echo "supervisorctl not found in PATH" >&2
  exit 1
fi

if [ -z "${COMMAND}" ]; then
  UV_BIN="${UV_BIN:-$(command -v uv || true)}"
  if [ -z "${UV_BIN}" ] && [ -n "${RUN_HOME}" ] && [ -x "${RUN_HOME}/.local/bin/uv" ]; then
    UV_BIN="${RUN_HOME}/.local/bin/uv"
  fi
  if [ -z "${UV_BIN}" ]; then
    echo "uv not found in PATH, please set COMMAND or UV_BIN explicitly." >&2
    exit 1
  fi
  COMMAND="${UV_BIN} run uvicorn app.main:app --host 0.0.0.0 --port ${BACKEND_PORT}"
fi

SUDO_CMD=""
if [ ! -w "${SUPERVISOR_CONF_DIR}" ]; then
  if command -v sudo >/dev/null 2>&1; then
    SUDO_CMD="sudo"
  else
    echo "Need write permission to ${SUPERVISOR_CONF_DIR} (and sudo is unavailable)." >&2
    exit 1
  fi
fi

mkdir -p "${APP_DIR}/logs"

if ! run_as_target_user test -w "${APP_DIR}/logs" >/dev/null 2>&1; then
  echo "Logs directory is not writable by ${RUN_USER}, fixing ownership..." >&2
  run_with_privilege chown -R "${RUN_USER}:${RUN_USER}" "${APP_DIR}/logs"
fi

if ! run_as_target_user test -w "${APP_DIR}/logs" >/dev/null 2>&1; then
  echo "Logs directory is still not writable by ${RUN_USER}: ${APP_DIR}/logs" >&2
  exit 1
fi

if ! run_as_target_user test -w "${APP_DIR}" >/dev/null 2>&1; then
  echo "Warning: ${APP_DIR} is not writable by ${RUN_USER}. If sqlite/db files need writes, startup may fail." >&2
fi

SERVICE_NAME_ESCAPED="$(escape_sed_replacement "${SERVICE_NAME}")"
APP_DIR_ESCAPED="$(escape_sed_replacement "${APP_DIR}")"
COMMAND_ESCAPED="$(escape_sed_replacement "${COMMAND}")"
RUN_USER_ESCAPED="$(escape_sed_replacement "${RUN_USER}")"

sed \
  -e "s|__SERVICE_NAME__|${SERVICE_NAME_ESCAPED}|g" \
  -e "s|__APP_DIR__|${APP_DIR_ESCAPED}|g" \
  -e "s|__COMMAND__|${COMMAND_ESCAPED}|g" \
  -e "s|__RUN_USER__|${RUN_USER_ESCAPED}|g" \
  "${TEMPLATE_PATH}" > "${GENERATED_CONF_PATH}"

echo "Generated supervisor config: ${GENERATED_CONF_PATH}"

run_with_privilege ln -sfn "${GENERATED_CONF_PATH}" "${TARGET_CONF_PATH}"
echo "Linked config: ${TARGET_CONF_PATH} -> ${GENERATED_CONF_PATH}"

run_with_privilege supervisorctl reread
run_with_privilege supervisorctl update

case "${ACTION}" in
  start)
    run_with_privilege supervisorctl start "${SERVICE_NAME}"
    ;;
  restart)
    if ! run_with_privilege supervisorctl restart "${SERVICE_NAME}"; then
      STATUS_OUTPUT="$(run_with_privilege supervisorctl status "${SERVICE_NAME}" || true)"
      if [[ "${STATUS_OUTPUT}" != *"RUNNING"* ]] && [[ "${STATUS_OUTPUT}" != *"STARTING"* ]]; then
        run_with_privilege supervisorctl start "${SERVICE_NAME}"
      fi
    fi
    ;;
  stop)
    run_with_privilege supervisorctl stop "${SERVICE_NAME}"
    ;;
  status)
    run_with_privilege supervisorctl status "${SERVICE_NAME}"
    ;;
  deploy)
    if ! run_with_privilege supervisorctl restart "${SERVICE_NAME}"; then
      STATUS_OUTPUT="$(run_with_privilege supervisorctl status "${SERVICE_NAME}" || true)"
      if [[ "${STATUS_OUTPUT}" != *"RUNNING"* ]] && [[ "${STATUS_OUTPUT}" != *"STARTING"* ]]; then
        run_with_privilege supervisorctl start "${SERVICE_NAME}"
      fi
    fi
    run_with_privilege supervisorctl status "${SERVICE_NAME}"
    ;;
  *)
    usage
    exit 1
    ;;
esac
