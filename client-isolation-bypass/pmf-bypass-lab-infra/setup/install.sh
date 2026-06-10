#!/usr/bin/env bash
# ==============================================================================
# PMF Bypass Lab — Environment Setup Script
# Target: Kali Linux (or Debian-based with Kali repos)
# Installs: mininet-wifi v2.0, hostapd, scapy, wireshark, kismet
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[-]${NC} $*"; exit 1; }

# ---- 1. System update & base deps ----
log "Updating package lists..."
apt-get update -y

log "Installing base dependencies..."
apt-get install -y \
    git curl wget build-essential \
    python3 python3-pip python3-dev \
    wireless-tools rfkill iw \
    net-tools iproute2 \
    tcpdump wireshark-common \
    isc-dhcp-server \
    kmod \
    openssh-server \
    --no-install-recommends

# ---- 2. Scapy ----
log "Installing Scapy..."
if python3 -c "import scapy" 2>/dev/null; then
    SCAPY_VER=$(python3 -c "import scapy; print(scapy.__version__)")
    warn "Scapy already installed via system packages (${SCAPY_VER}) — skipping pip install"
else
    pip3 install --break-system-packages scapy
fi

# ---- 3. hostapd & wpasupplicant ----
log "Installing hostapd and wpasupplicant..."
apt-get install -y hostapd wpasupplicant

# ---- 4. mininet-wifi ----
patch_mininet_python3() {
  # v2.0 tag still ships Python-2-era mininet snippets; fix for Python 3.11+
  find /opt/mininet-wifi/mininet /opt/mininet-wifi/mn_wifi -name '*.py' 2>/dev/null \
    | while read -r py; do
        sed -i \
          -e '/from __builtin__ import True/d' \
          -e '/from __builtin__ import False/d' \
          -e 's/from __builtin__ import range/from builtins import range/g' \
          "$py"
      done
}

install_wmediumd_userspace() {
  if command -v wmediumd &>/dev/null; then
    return 0
  fi
  log "Building wmediumd (userspace only — kernel hwsim already present)..."
  apt-get install -y libnl-3-dev libnl-genl-3-dev pkg-config libconfig-dev
  local src=/tmp/wmediumd-build
  rm -rf "$src"
  git clone --depth 1 https://github.com/cozybit/wmediumd.git "$src"
  make -C "$src/wmediumd"
  install -m 0755 "$src/wmediumd/wmediumd" /usr/local/bin/wmediumd
}

install_mininet_wifi_kali() {
  log "Kali detected — manual mininet-wifi install (Python 3.13 compatible)..."
  apt-get install -y \
    openvswitch-switch openvswitch-common \
    cgroup-tools iproute2 ethtool \
    python3-setuptools python3-urllib3 python3-matplotlib \
    xterm help2man

  systemctl enable --now openvswitch-switch 2>/dev/null || true

  cd /opt/mininet-wifi
  # master has newer fixes than v2.0 tag on Python 3.13
  if git rev-parse --is-inside-work-tree &>/dev/null; then
    git fetch origin master --depth 1 2>/dev/null || true
    git checkout master 2>/dev/null || warn "stay on current mininet-wifi checkout"
  fi

  patch_mininet_python3
  install_wmediumd_userspace

  pip3 install -e . --break-system-packages

  if [ -f /opt/mininet-wifi/mn ]; then
    ln -sf /opt/mininet-wifi/mn /usr/local/bin/mn
  fi
}

log "Installing mininet-wifi..."
if [ ! -d "/opt/mininet-wifi" ]; then
  if grep -qi kali /etc/os-release 2>/dev/null; then
    git clone --depth 1 https://github.com/intrig-unicamp/mininet-wifi.git /opt/mininet-wifi
  else
    git clone --branch v2.0 --depth 1 \
      https://github.com/intrig-unicamp/mininet-wifi.git /opt/mininet-wifi
  fi
fi

if grep -qi kali /etc/os-release 2>/dev/null; then
  install_mininet_wifi_kali
else
  cd /opt/mininet-wifi
  util/install.sh -Wlnfv
fi

# ---- 5. Kismet ----
log "Installing Kismet..."
apt-get install -y kismet

# ---- 6. Enable mac80211_hwsim (kernel module, not an apt package) ----
log "Loading mac80211_hwsim kernel module..."
if modinfo mac80211_hwsim &>/dev/null; then
    modprobe mac80211_hwsim radios=4 2>/dev/null || modprobe mac80211_hwsim || warn "mac80211_hwsim load failed"
else
    warn "mac80211_hwsim not in kernel — install linux-headers-\$(uname -r) and reboot"
fi

# ---- 7. Verification ----
log ""
log "========================= VERIFICATION ========================="

echo -n "Python3:       "; python3 --version 2>&1 || err "python3 missing"
echo -n "pip3:          "; pip3 --version 2>&1 || warn "pip3 check failed"
echo -n "Scapy:         "; python3 -c "import scapy; print(scapy.__version__)" 2>&1 || err "scapy import failed"
echo -n "hostapd:       "; hostapd -v 2>&1 | head -1 || warn "hostapd missing"
echo -n "wpa_supplicant:"; wpa_supplicant -v 2>&1 | head -1 || warn "wpa_supplicant missing"
echo -n "Kismet:        "; kismet --version 2>&1 | head -1 || warn "kismet missing"
echo -n "hwsim radios:  "; iw dev 2>&1 | grep -c "Interface" || warn "no hwsim radios"
echo -n "mininet-wifi:  "; python3 -c "import mn_wifi; print('ok')" 2>&1 || warn "mininet-wifi import failed"
echo -n "mn command:    "; command -v mn && mn --version 2>&1 | head -1 || warn "mn not in PATH"

log ""
log "Setup complete."
log "Next: run setup/ssh_setup.sh for agent SSH access."
