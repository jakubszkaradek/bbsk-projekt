#!/usr/bin/env bash
# ==============================================================================
# PMF Bypass Lab — SSH Setup for AI Agents
# Creates dedicated 'agent' user with SSH key access.
# VMware NAT Port Forwarding: host:2222 → VM:22
# ==============================================================================
set -euo pipefail

AGENT_USER="agent"
AGENT_HOME="/home/${AGENT_USER}"
SSH_KEY_COMMENT="pmf-lab-agent"

GREEN='\033[0;32m'
NC='\033[0m'
log() { echo -e "${GREEN}[+]${NC} $*"; }

# ---- 1. Ensure SSH server is running ----
log "Installing & enabling SSH server..."
apt-get install -y openssh-server
systemctl enable ssh
systemctl start ssh

# ---- 2. Create agent user ----
if id "${AGENT_USER}" &>/dev/null; then
    log "User '${AGENT_USER}' already exists — skipping creation"
else
    log "Creating user '${AGENT_USER}'..."
    useradd -m -s /bin/bash "${AGENT_USER}"
    usermod -aG sudo "${AGENT_USER}"
    # Passwordless sudo for agent
    echo "${AGENT_USER} ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/${AGENT_USER}"
    chmod 0440 "/etc/sudoers.d/${AGENT_USER}"
fi

# ---- 3. Set up SSH key directory ----
log "Setting up SSH key directory..."
mkdir -p "${AGENT_HOME}/.ssh"
chmod 700 "${AGENT_HOME}/.ssh"
chown -R "${AGENT_USER}:${AGENT_USER}" "${AGENT_HOME}/.ssh"

# ---- 4. Generate SSH key pair (if not existing) ----
if [ ! -f "${AGENT_HOME}/.ssh/id_ed25519" ]; then
    log "Generating ed25519 key pair..."
    su - "${AGENT_USER}" -c "ssh-keygen -t ed25519 -N '' -C '${SSH_KEY_COMMENT}' -f ~/.ssh/id_ed25519"
fi

# ---- 5. Authorize the key ----
cat "${AGENT_HOME}/.ssh/id_ed25519.pub" >> "${AGENT_HOME}/.ssh/authorized_keys"
chmod 600 "${AGENT_HOME}/.ssh/authorized_keys"
chown "${AGENT_USER}:${AGENT_USER}" "${AGENT_HOME}/.ssh/authorized_keys"

# ---- 6. Harden SSH config for agent ----
log "Hardening SSH daemon config..."
SSHD_CFG="/etc/ssh/sshd_config"

# Backup original
cp "${SSHD_CFG}" "${SSHD_CFG}.bak"

sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' "${SSHD_CFG}"
sed -i 's/^#*PubkeyAuthentication.*/PubkeyAuthentication yes/' "${SSHD_CFG}"
sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' "${SSHD_CFG}"

# Restart SSH
systemctl restart ssh

# ---- 7. Print connection info & agent key ----
log ""
log "===================== SSH SETUP COMPLETE ====================="
log ""
log "Private key (copy this to the AI agent host):"
echo ""
cat "${AGENT_HOME}/.ssh/id_ed25519"
echo ""
log "=============================================================="
log "VMware NAT Port Forwarding (configure in VMware):"
log "  Host Port:  2222"
log "  VM Port:    22"
log "  Protocol:   TCP"
log ""
log "Test connection from host:"
log "  ssh -i /path/to/saved/private_key -p 2222 agent@localhost"
log ""
log "IMPORTANT: After copying the private key, delete it from VM:"
log "  shred -u ${AGENT_HOME}/.ssh/id_ed25519"
log "=============================================================="
