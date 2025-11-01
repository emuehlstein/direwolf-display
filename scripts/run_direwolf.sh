#!/usr/bin/env bash
set -euo pipefail

: "${RTLFM_DEVICE:=0}"
: "${RTLFM_FREQUENCY:=144.390M}"
: "${RTLFM_SAMPLE_RATE:=48000}"
: "${RTLFM_GAIN:=49.6}"
: "${RTLFM_PPM:=0}"
: "${RTLFM_EXTRA_OPTS:=-l 0 -E deemp -E dc}"
: "${DIREWOLF_CONFIG:=/etc/direwolf.conf}"
: "${DIREWOLF_EXTRA_OPTS:=-l /var/log/direwolf}"

rtl_fm_cmd=(
  /usr/bin/rtl_fm
  -d "${RTLFM_DEVICE}"
  -f "${RTLFM_FREQUENCY}"
  -s "${RTLFM_SAMPLE_RATE}"
  -g "${RTLFM_GAIN}"
  -p "${RTLFM_PPM}"
  -M fm
  -A fast
)

if [[ -n "${RTLFM_EXTRA_OPTS}" ]]; then
  # shellcheck disable=SC2206 # word-splitting is intentional for extra options
  rtl_fm_cmd+=(${RTLFM_EXTRA_OPTS})
fi

direwolf_cmd=(
  /usr/bin/direwolf
  -r "${RTLFM_SAMPLE_RATE}"
  -c "${DIREWOLF_CONFIG}"
  -t 0
)

if [[ -n "${DIREWOLF_EXTRA_OPTS}" ]]; then
  # shellcheck disable=SC2206 # word-splitting is intentional for extra options
  direwolf_cmd+=(${DIREWOLF_EXTRA_OPTS})
fi

direwolf_cmd+=(-)

exec "${rtl_fm_cmd[@]}" - | "${direwolf_cmd[@]}"
