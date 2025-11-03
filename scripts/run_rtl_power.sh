#!/usr/bin/env bash
set -euo pipefail

: "${RTL_POWER_ENABLE:=0}"
: "${RTL_POWER_FREQUENCY_MHZ:=144.390}"
: "${RTL_POWER_SPAN_KHZ:=0}"
: "${RTL_POWER_BIN_WIDTH_HZ:=2000}"
: "${RTL_POWER_INTEGRATION:=5}"
: "${RTL_POWER_INTERVAL:=30}"
: "${RTL_POWER_GAIN:=}"
: "${RTL_POWER_PPM:=}"
: "${RTL_POWER_BATCH_SIZE:=6}"
: "${RTL_POWER_POST_URL:=http://127.0.0.1:9090/v1}"
: "${RTL_POWER_ADDITIONAL_ARGS:=}"
: "${UV_PROJECT_ENV:=/opt/direwolf-display/.venv}"
: "${UV_BIN:=/usr/local/bin/uv}"

enable_value="$(printf '%s' "${RTL_POWER_ENABLE}" | tr '[:upper:]' '[:lower:]')"
if [[ "${enable_value}" == "0" || "${enable_value}" == "false" ]]; then
  echo "[run_rtl_power] RTL_POWER_ENABLE disabled; exiting." >&2
  exit 0
fi

if [[ ! -x "${UV_BIN}" ]]; then
  UV_BIN="$(command -v uv || true)"
fi
if [[ -z "${UV_BIN}" ]]; then
  echo "[run_rtl_power] ERROR: uv command not found" >&2
  exit 1
fi

cmd=(
  "${UV_BIN}"
  run
  python
  tools/rtl_power_monitor.py
  --frequency-mhz "${RTL_POWER_FREQUENCY_MHZ}"
  --span-khz "${RTL_POWER_SPAN_KHZ}"
  --bin-width-hz "${RTL_POWER_BIN_WIDTH_HZ}"
  --integration "${RTL_POWER_INTEGRATION}"
  --interval "${RTL_POWER_INTERVAL}"
  --batch-size "${RTL_POWER_BATCH_SIZE}"
  --post-url "${RTL_POWER_POST_URL}"
  --no-stdout
)

if [[ -n "${RTL_POWER_GAIN}" ]]; then
  cmd+=(--gain "${RTL_POWER_GAIN}")
fi
if [[ -n "${RTL_POWER_PPM}" ]]; then
  cmd+=(--ppm "${RTL_POWER_PPM}")
fi

if [[ -n "${RTL_POWER_ADDITIONAL_ARGS}" ]]; then
  # shellcheck disable=SC2206 # intentional word splitting for additional args
  extra_args=(${RTL_POWER_ADDITIONAL_ARGS})
  cmd+=("--" "${extra_args[@]}")
fi

echo "[run_rtl_power] Executing: ${cmd[*]}" >&2
exec "${cmd[@]}"
