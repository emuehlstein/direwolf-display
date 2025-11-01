#!/usr/bin/env bash
set -euo pipefail

# Usage: ./pi_postinstall.sh [/path/to/direwolf_display]
# Default assumes the repository already exists at /opt/direwolf_display-src.

REPO_DIR="${1:-/opt/direwolf_display-src}"
PLAYBOOK="infra/ansible/site.yml"
INVENTORY="infra/ansible/inventory.ini"

if [[ $EUID -ne 0 ]]; then
  echo "This script must run as root (it installs packages and configures systemd)." >&2
  exit 1
fi

if [[ ! -d "$REPO_DIR" ]]; then
  echo "Repository directory not found at $REPO_DIR" >&2
  echo "Clone the project first, for example:" >&2
  echo "  git clone https://github.com/your-org/direwolf_display.git $REPO_DIR" >&2
  exit 1
fi

cd "$REPO_DIR"

echo "[pi_postinstall] Updating apt cache and installing dependencies"
apt-get update
apt-get install -y ansible git rsync python3 python3-venv python3-pip curl

echo "[pi_postinstall] Installing required Ansible collections"
ansible-galaxy collection install ansible.posix

echo "[pi_postinstall] Running Ansible playbook"
ansible-playbook -i "$INVENTORY" "$PLAYBOOK" \
  --extra-vars "direwolf_display_repo_src=$REPO_DIR"

echo "[pi_postinstall] Provisioning complete. Services should now be active."
