#!/usr/bin/env bash
set -euo pipefail

: "${DIREWOLF_CONFIG:=/etc/direwolf.conf}"
: "${DIREWOLF_SAMPLE_RATE:=48000}"
: "${DIREWOLF_EXTRA_OPTS:=-l /var/log/direwolf}"
: "${SA818_ENABLE:=1}"
: "${SA818_PORT:=/dev/ttyUSB0}"
: "${SA818_SPEED:=9600}"
: "${SA818_FREQUENCY:=144.390}"
: "${SA818_OFFSET:=0}"
: "${SA818_BANDWIDTH:=wide}"
: "${SA818_SQUELCH:=4}"
: "${SA818_CTCSS:=}"
: "${SA818_DCS:=}"
: "${SA818_TAIL:=}"
: "${SA818_VOLUME:=}"
: "${SA818_EMPHASIS:=}"
: "${SA818_HIGHPASS:=}"
: "${SA818_LOWPASS:=}"
: "${UV_BIN:=/usr/local/bin/uv}"

if [[ ! -x "${UV_BIN}" ]]; then
  UV_BIN="$(command -v uv || true)"
fi

sa818_enable_value="$(printf '%s' "${SA818_ENABLE}" | tr '[:upper:]' '[:lower:]')"
if [[ "${sa818_enable_value}" != "0" && "${sa818_enable_value}" != "false" ]]; then
  if [[ -z "${UV_BIN}" ]]; then
    echo "[run_direwolf] WARNING: uv binary not found, skipping SA818 programming" >&2
  elif [[ -z "${SA818_FREQUENCY}" ]]; then
    echo "[run_direwolf] WARNING: SA818_FREQUENCY not set, skipping SA818 programming" >&2
  else
    declare -a sa818_cmd_base=("${UV_BIN}" run -- sa818)
    if [[ -n "${SA818_PORT}" ]]; then
      sa818_cmd_base+=(--port "${SA818_PORT}")
    fi
    if [[ -n "${SA818_SPEED}" ]]; then
      sa818_cmd_base+=(--speed "${SA818_SPEED}")
    fi

    sa818_bw_lower="$(printf '%s' "${SA818_BANDWIDTH}" | tr '[:upper:]' '[:lower:]')"
    case "${sa818_bw_lower}" in
      narrow|0)
        sa818_bw_flag=0
        ;;
      wide|1|"")
        sa818_bw_flag=1
        ;;
      *)
        echo "[run_direwolf] WARNING: Unknown SA818_BANDWIDTH '${SA818_BANDWIDTH}', defaulting to wide" >&2
        sa818_bw_flag=1
        ;;
    esac

    declare -a radio_args=(radio --frequency "${SA818_FREQUENCY}" --bw "${sa818_bw_flag}")
    if [[ -n "${SA818_OFFSET}" && "${SA818_OFFSET}" != "0" && "${SA818_OFFSET}" != "0.0" ]]; then
      radio_args+=(--offset "${SA818_OFFSET}")
    fi
    if [[ -n "${SA818_SQUELCH}" ]]; then
      radio_args+=(--squelch "${SA818_SQUELCH}")
    fi

    if [[ -n "${SA818_CTCSS}" ]]; then
      sa818_ctcss_lower="$(printf '%s' "${SA818_CTCSS}" | tr '[:upper:]' '[:lower:]')"
      if [[ "${sa818_ctcss_lower}" != "none" ]]; then
        radio_args+=(--ctcss "${SA818_CTCSS}")
      fi
    elif [[ -n "${SA818_DCS}" ]]; then
      radio_args+=(--dcs "${SA818_DCS}")
    fi

    if [[ -n "${SA818_TAIL}" ]]; then
      radio_args+=(--tail "${SA818_TAIL}")
    fi

    if ! "${sa818_cmd_base[@]}" "${radio_args[@]}"; then
      echo "[run_direwolf] WARNING: Failed to configure SA818 radio" >&2
    fi

    if [[ -n "${SA818_VOLUME}" ]]; then
      if ! "${sa818_cmd_base[@]}" volume --level "${SA818_VOLUME}"; then
        echo "[run_direwolf] WARNING: Failed to set SA818 volume" >&2
      fi
    fi

    if [[ -n "${SA818_EMPHASIS}" && -n "${SA818_HIGHPASS}" && -n "${SA818_LOWPASS}" ]]; then
      if ! "${sa818_cmd_base[@]}" filters --emphasis "${SA818_EMPHASIS}" --highpass "${SA818_HIGHPASS}" --lowpass "${SA818_LOWPASS}"; then
        echo "[run_direwolf] WARNING: Failed to set SA818 filters" >&2
      fi
    fi
  fi
fi

direwolf_cmd=(
  /usr/bin/direwolf
  -r "${DIREWOLF_SAMPLE_RATE}"
  -c "${DIREWOLF_CONFIG}"
  -t 0
)

if [[ -n "${DIREWOLF_EXTRA_OPTS}" ]]; then
  # shellcheck disable=SC2206 # word-splitting is intentional for extra options
  direwolf_cmd+=(${DIREWOLF_EXTRA_OPTS})
fi

exec "${direwolf_cmd[@]}"
