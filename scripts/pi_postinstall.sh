#!/usr/bin/env bash
set -euo pipefail

# Usage: ./pi_postinstall.sh [--callsign <CALLSIGN>] [/path/to/direwolf-display]
# Default assumes the repository already exists at /opt/direwolf-display-src.

REPO_DIR="/opt/direwolf-display-src"
CALLSIGN=""
PLAYBOOK="infra/ansible/site.yml"
INVENTORY="infra/ansible/inventory.ini"
DIGIPEATER=false
DIGI_MATCH=""
DIGI_REPLACE=""
DIGI_OPTIONS=""
RX_IGATE=false
IGATE_SERVER=""
IGATE_LOGIN=""
IGATE_PASSCODE=""
IGATE_FILTER=""

generate_aprs_passcode() {
  local call="$1"
  if ! command -v python3 >/dev/null 2>&1; then
    return 1
  fi
  python3 -m tools.aprs_passcode --callsign "$call"
}

usage() {
  cat <<'EOF'
Usage: pi_postinstall.sh [options] [repo_dir]

Options:
  --callsign <CALLSIGN>  Set the Direwolf MYCALL value during provisioning.
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

If repo_dir is omitted, /opt/direwolf-display-src is assumed.
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
      REPO_DIR="$1"
      shift
      ;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  echo "This script must run as root (it installs packages and configures systemd)." >&2
  exit 1
fi

if [[ ! -d "$REPO_DIR" ]]; then
  echo "Repository directory not found at $REPO_DIR" >&2
  echo "Clone the project first, for example:" >&2
  echo "  git clone https://github.com/emuehlstein/direwolf-display.git $REPO_DIR" >&2
  exit 1
fi

cd "$REPO_DIR"

echo "[pi_postinstall] Updating apt cache and installing dependencies"
apt update
apt install -y ansible git rsync python3 python3-venv python3-pip curl

echo "[pi_postinstall] Installing required Ansible collections"
ansible-galaxy collection install ansible.posix

echo "[pi_postinstall] Running Ansible playbook"
extra_vars=("direwolf_display_repo_src=$REPO_DIR")
if [[ -n "$CALLSIGN" ]]; then
  extra_vars+=("direwolf_callsign=$CALLSIGN")
fi
if [[ "$DIGIPEATER" == true ]]; then
  extra_vars+=("direwolf_enable_digipeater=true")
  if [[ -n "$DIGI_MATCH" ]]; then
    extra_vars+=("direwolf_digipeater_match=$DIGI_MATCH")
  fi
  if [[ -n "$DIGI_REPLACE" ]]; then
    extra_vars+=("direwolf_digipeater_replace=$DIGI_REPLACE")
  fi
  if [[ -n "$DIGI_OPTIONS" ]]; then
    extra_vars+=("direwolf_digipeater_options=$DIGI_OPTIONS")
  fi
fi
if [[ "$RX_IGATE" == true ]]; then
  extra_vars+=("direwolf_enable_igate_rx=true")
  if [[ -n "$IGATE_SERVER" ]]; then
    extra_vars+=("direwolf_igate_server=$IGATE_SERVER")
  fi
  if [[ -n "$IGATE_LOGIN" ]]; then
    extra_vars+=("direwolf_igate_login=$IGATE_LOGIN")
  fi
  passcode_to_use="$IGATE_PASSCODE"
  if [[ -z "$passcode_to_use" ]]; then
    login_call="${IGATE_LOGIN:-${CALLSIGN:-}}"
    if [[ -n "$login_call" ]]; then
      if generated_passcode=$(generate_aprs_passcode "$login_call" 2>/dev/null); then
        passcode_to_use="$generated_passcode"
        echo "[pi_postinstall] Generated APRS-IS passcode for ${login_call}" >&2
      else
        echo "[pi_postinstall] WARNING: Unable to generate APRS-IS passcode automatically." >&2
      fi
    else
      echo "[pi_postinstall] WARNING: IGate enabled but no login callsign provided; cannot generate passcode." >&2
    fi
  fi
  if [[ -n "$passcode_to_use" ]]; then
    extra_vars+=("direwolf_igate_passcode=$passcode_to_use")
  else
    echo "[pi_postinstall] WARNING: IGate enabled but no passcode provided; APRS-IS login will be skipped." >&2
  fi
  if [[ -n "$IGATE_FILTER" ]]; then
    extra_vars+=("direwolf_igate_filter=$IGATE_FILTER")
  fi
fi
ansible_args=()
for var in "${extra_vars[@]}"; do
  ansible_args+=(--extra-vars "$var")
done
ansible-playbook -i "$INVENTORY" "$PLAYBOOK" "${ansible_args[@]}"

echo "[pi_postinstall] Provisioning complete. Services should now be active."
