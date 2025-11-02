#!/usr/bin/env bash
set -euo pipefail

: "${DIREWOLF_CONFIG:=/etc/direwolf.conf}"
: "${DIREWOLF_SAMPLE_RATE:=48000}"
: "${DIREWOLF_EXTRA_OPTS:=-l /var/log/direwolf}"
: "${SHARIPI_FREQ_CMD:=}"
: "${SHARIPI_FREQ_ARGS:=}"

direwolf_cmd=(
  /usr/bin/direwolf
  -r "${DIREWOLF_SAMPLE_RATE}"
  -c "${DIREWOLF_CONFIG}"
)

if [[ -n "${DIREWOLF_EXTRA_OPTS}" ]]; then
  # shellcheck disable=SC2206 # word-splitting is intentional for extra options
  direwolf_cmd+=(${DIREWOLF_EXTRA_OPTS})
fi

if [[ -n "${SHARIPI_FREQ_CMD}" ]]; then
  # shellcheck disable=SC2206
  freq_cmd=(${SHARIPI_FREQ_CMD})
  if [[ -n "${SHARIPI_FREQ_ARGS}" ]]; then
    # shellcheck disable=SC2206
    freq_cmd+=(${SHARIPI_FREQ_ARGS})
  fi

  echo "[run_direwolf] Setting SharPi frequency via: ${freq_cmd[*]}" >&2
  "${freq_cmd[@]}"
fi

exec "${direwolf_cmd[@]}"
