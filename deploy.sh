#!/usr/bin/env bash
# One-shot deploy: rsync source -> build on server -> install systemd unit -> cleanup.
#
# Usage:
#   bash deploy.sh user@host                 # uses defaults below
#   bash deploy.sh user@host /opt/attendance # custom install dir
#
# Run from your local machine (Git Bash / WSL on Windows). Requires:
#   - ssh + rsync on the local side
#   - sudo access for the SSH user on the server (for systemd install)

set -euo pipefail

# ─── Args ──────────────────────────────────────────────────────────────────
if [ $# -lt 1 ]; then
    echo "Usage: bash deploy.sh user@host [install_dir]" >&2
    echo "Example: bash deploy.sh ubuntu@13.126.47.172 /home/ubuntu/attendance" >&2
    exit 1
fi

REMOTE="$1"
INSTALL_DIR="${2:-/home/ubuntu/attendance}"
BUILD_DIR="/tmp/juteatt-build-$$"
SERVICE_NAME="juteatt"

echo "================================================"
echo " Deploy target : $REMOTE"
echo " Install dir   : $INSTALL_DIR"
echo " Build dir     : $BUILD_DIR  (temporary, on server)"
echo "================================================"
echo

# ─── 1. Sync source to a temp dir on the server ────────────────────────────
echo "[1/5] Uploading source to $REMOTE:$BUILD_DIR ..."
ssh "$REMOTE" "mkdir -p '$BUILD_DIR'"

rsync -az --info=progress2 \
    --exclude='venv/' \
    --exclude='.venv/' \
    --exclude='build/' \
    --exclude='__pycache__/' \
    --exclude='.git/' \
    --exclude='*.log' \
    --exclude='*.rar' \
    --exclude='*.backup_*' \
    --exclude='employee_photos/' \
    --exclude='img/' \
    --exclude='*.md' \
    --exclude='test_*' \
    --exclude='*.txt' \
    --exclude='*.bat' \
    --exclude='*.ps1' \
    --exclude='deploy.sh' \
    --include='requirements.txt' \
    "$(dirname "$0")/" "$REMOTE:$BUILD_DIR/"

# rsync excludes win over includes by order, so re-push requirements.txt explicitly.
scp -q "$(dirname "$0")/requirements.txt" "$REMOTE:$BUILD_DIR/requirements.txt"

# ─── 2. Build on server ────────────────────────────────────────────────────
echo
echo "[2/5] Building onefile binary on server (this takes several minutes)..."
ssh "$REMOTE" "cd '$BUILD_DIR' && bash build.sh"

# ─── 3. Install binary ─────────────────────────────────────────────────────
echo
echo "[3/5] Installing binary to $INSTALL_DIR ..."
ssh "$REMOTE" "
    sudo mkdir -p '$INSTALL_DIR' &&
    sudo mv '$BUILD_DIR/build/juteatt' '$INSTALL_DIR/juteatt' &&
    sudo chmod +x '$INSTALL_DIR/juteatt' &&
    sudo mkdir -p '$INSTALL_DIR/employee_photos' '$INSTALL_DIR/img' &&
    sudo chown -R \$(whoami):\$(whoami) '$INSTALL_DIR'
"

# ─── 4. Install systemd unit ───────────────────────────────────────────────
echo
echo "[4/5] Installing systemd unit ${SERVICE_NAME}.service ..."
# Patch the unit file's WorkingDirectory/ExecStart/User to match this deploy.
REMOTE_USER="${REMOTE%@*}"
ssh "$REMOTE" "
    sudo cp '$BUILD_DIR/juteatt.service' /etc/systemd/system/${SERVICE_NAME}.service &&
    sudo sed -i \
        -e 's|^User=.*|User=${REMOTE_USER}|' \
        -e 's|^Group=.*|Group=${REMOTE_USER}|' \
        -e 's|^WorkingDirectory=.*|WorkingDirectory=${INSTALL_DIR}|' \
        -e 's|^ExecStart=.*|ExecStart=${INSTALL_DIR}/juteatt|' \
        -e 's|^ReadWritePaths=.*|ReadWritePaths=${INSTALL_DIR} /var/tmp|' \
        /etc/systemd/system/${SERVICE_NAME}.service &&
    sudo systemctl daemon-reload &&
    sudo systemctl enable ${SERVICE_NAME} &&
    sudo systemctl restart ${SERVICE_NAME}
"

# ─── 5. Cleanup ────────────────────────────────────────────────────────────
echo
echo "[5/5] Cleaning up source from server..."
ssh "$REMOTE" "rm -rf '$BUILD_DIR'"

echo
echo "================================================"
echo " Deploy complete."
echo "================================================"
ssh "$REMOTE" "sudo systemctl status ${SERVICE_NAME} --no-pager -l | head -20"
echo
echo "Tail logs with:"
echo "  ssh $REMOTE 'sudo journalctl -u ${SERVICE_NAME} -f'"
