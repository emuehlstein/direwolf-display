#!/usr/bin/env bash
set -euo pipefail

DEFAULT_REPO_DIR="/opt/direwolf-display-src"
REPO_DIR="$DEFAULT_REPO_DIR"
CALLSIGN=""
DIGIPEATER=false
DIGI_MATCH=""
DIGI_REPLACE=""
DIGI_OPTIONS=""
RX_IGATE=false
IGATE_SERVER=""
IGATE_LOGIN=""
IGATE_PASSCODE=""
IGATE_FILTER=""
LAT_DEC=""
LON_DEC=""
BEACON_COMMENT=""

usage() {
  cat <<'EOF'
Usage: firstrun.sh [options]

Options:
  --callsign <CALLSIGN>  Seed the Direwolf MYCALL value during provisioning.
  --dest <PATH>          Destination for the repository clone (default: /opt/direwolf-display-src).
  --lat <DECIMAL>        Latitude in decimal degrees (e.g., 33.7991).
  --lon <DECIMAL>        Longitude in decimal degrees (e.g., -84.2935).
  --comment <TEXT>       APRS beacon comment text.
  --digipeater           Enable standard WIDEn-N digipeating (defaults provided).
  --digipeater-match <PATTERN>
                         Override the incoming path match regex.
  --digipeater-replace <PATTERN>
                         Override the outgoing substitution string.
  --digipeater-options <OPTIONS>
                         Additional digipeater options (e.g., TRACE).
  --rx-igate             Enable receive-only APRS-IS gateway.
  --igate-server <HOST>  Override APRS-IS Tier 2 server (default: noam.aprs2.net).
  --igate-login <CALL>   Login call for APRS-IS (defaults to MYCALL when omitted).
  --igate-passcode <CODE>
                         APRS-IS passcode (auto-generated from callsign when omitted).
  --igate-filter <EXPR>  Optional server-side filter.
  -h, --help             Show this message and exit.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --callsign|-c)
      if [[ $# -lt 2 ]]; then
        echo "Error: --callsign requires a value." >&2
        exit 1
      fi
      CALLSIGN="$2"
      shift 2
      ;;
    --lat)
      if [[ $# -lt 2 ]]; then
        echo "Error: --lat requires a value." >&2
        exit 1
      fi
      LAT_DEC="$2"
      shift 2
      ;;
    --lon)
      if [[ $# -lt 2 ]]; then
        echo "Error: --lon requires a value." >&2
        exit 1
      fi
      LON_DEC="$2"
      shift 2
      ;;
    --comment)
      if [[ $# -lt 2 ]]; then
        echo "Error: --comment requires a value." >&2
        exit 1
      fi
      BEACON_COMMENT="$2"
      shift 2
      ;;
    --dest|-d)
      if [[ $# -lt 2 ]]; then
        echo "Error: --dest requires a value." >&2
        exit 1
      fi
      REPO_DIR="$2"
      shift 2
      ;;
    --digipeater)
      DIGIPEATER=true
      shift
      ;;
    --digipeater-match)
      if [[ $# -lt 2 ]]; then
        echo "Error: --digipeater-match requires a value." >&2
        exit 1
      fi
      DIGI_MATCH="$2"
      shift 2
      ;;
    --digipeater-replace)
      if [[ $# -lt 2 ]]; then
        echo "Error: --digipeater-replace requires a value." >&2
        exit 1
      fi
      DIGI_REPLACE="$2"
      shift 2
      ;;
    --digipeater-options)
      if [[ $# -lt 2 ]]; then
        echo "Error: --digipeater-options requires a value." >&2
        exit 1
      fi
      DIGI_OPTIONS="$2"
      shift 2
      ;;
    --rx-igate)
      RX_IGATE=true
      shift
      ;;
    --igate-server)
      if [[ $# -lt 2 ]]; then
        echo "Error: --igate-server requires a value." >&2
        exit 1
      fi
      IGATE_SERVER="$2"
      shift 2
      ;;
    --igate-login)
      if [[ $# -lt 2 ]]; then
        echo "Error: --igate-login requires a value." >&2
        exit 1
      fi
      IGATE_LOGIN="$2"
      shift 2
      ;;
    --igate-passcode)
      if [[ $# -lt 2 ]]; then
        echo "Error: --igate-passcode requires a value." >&2
        exit 1
      fi
      IGATE_PASSCODE="$2"
      shift 2
      ;;
    --igate-filter)
      if [[ $# -lt 2 ]]; then
        echo "Error: --igate-filter requires a value." >&2
        exit 1
      fi
      IGATE_FILTER="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
    *)
      echo "Unexpected positional argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -n "$LAT_DEC" && -z "$LON_DEC" ]] || [[ -z "$LAT_DEC" && -n "$LON_DEC" ]]; then
  echo "Error: --lat and --lon must be provided together." >&2
  exit 1
fi

if [[ -d "$REPO_DIR" ]]; then
  echo "[firstrun] Repository already exists at $REPO_DIR"
else
  echo "[firstrun] Cloning Direwolf Display repository into $REPO_DIR"
  git clone https://github.com/emuehlstein/direwolf-display.git "$REPO_DIR"
fi

postinstall_args=()
if [[ -n "$CALLSIGN" ]]; then
  postinstall_args+=(--callsign "$CALLSIGN")
fi
if [[ -n "$LAT_DEC" ]]; then
  postinstall_args+=(--lat "$LAT_DEC" --lon "$LON_DEC")
fi
if [[ -n "$BEACON_COMMENT" ]]; then
  postinstall_args+=(--comment "$BEACON_COMMENT")
fi
if [[ "$DIGIPEATER" == true ]]; then
  postinstall_args+=(--digipeater)
  if [[ -n "$DIGI_MATCH" ]]; then
    postinstall_args+=(--digipeater-match "$DIGI_MATCH")
  fi
  if [[ -n "$DIGI_REPLACE" ]]; then
    postinstall_args+=(--digipeater-replace "$DIGI_REPLACE")
  fi
  if [[ -n "$DIGI_OPTIONS" ]]; then
    postinstall_args+=(--digipeater-options "$DIGI_OPTIONS")
  fi
fi
if [[ "$RX_IGATE" == true ]]; then
  postinstall_args+=(--rx-igate)
  if [[ -n "$IGATE_SERVER" ]]; then
    postinstall_args+=(--igate-server "$IGATE_SERVER")
  fi
  postinstall_login="${IGATE_LOGIN:-${CALLSIGN:-}}"
  if [[ -n "$postinstall_login" ]]; then
    postinstall_args+=(--igate-login "$postinstall_login")
  fi
  if [[ -n "$IGATE_PASSCODE" ]]; then
    postinstall_args+=(--igate-passcode "$IGATE_PASSCODE")
  fi
  if [[ -n "$IGATE_FILTER" ]]; then
    postinstall_args+=(--igate-filter "$IGATE_FILTER")
  fi
fi
postinstall_args+=("$REPO_DIR")

echo "[firstrun] Running post-install script"
bash "$REPO_DIR/scripts/pi_postinstall.sh" "${postinstall_args[@]}"

echo "[firstrun] Setup complete."
