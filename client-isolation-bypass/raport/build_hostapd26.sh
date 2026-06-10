#!/bin/bash
# ==============================================================================
# Build hostapd 2.6 from source
# 
# hostapd 2.6 classifies CSA (Channel Switch Announcement) as NON-ROBUST,
# meaning it's NOT protected by PMF. This is the vulnerable version we need
# for the CSA injection exploit.
#
# Installs to /opt/hostapd-2.6/ (does NOT replace system hostapd 2.10)
# ==============================================================================
set -e

HOSTAPD_VERSION="hostap_2_6"
INSTALL_DIR="/opt/hostapd-2.6"
BUILD_DIR="/tmp/hostapd-build-2.6"

echo "=== Building hostapd 2.6 ==="

# 1. Install build deps
echo "[1/6] Installing build dependencies..."
sudo apt-get install -y build-essential libssl-dev libnl-3-dev libnl-genl-3-dev pkg-config 2>/dev/null | tail -2

# 2. Clone hostapd
echo "[2/6] Cloning hostapd source..."
if [ -d "$BUILD_DIR" ]; then
    sudo rm -rf "$BUILD_DIR"
fi
git clone --depth 1 --branch "$HOSTAPD_VERSION" https://w1.fi/hostap.git "$BUILD_DIR" 2>&1 | tail -2

# 3. Configure build
echo "[3/6] Configuring hostapd 2.6..."
cd "$BUILD_DIR/hostapd"
cp defconfig .config

# Enable key features
cat >> .config << 'EOF'
CONFIG_DRIVER_NL80211=y
CONFIG_LIBNL32=y
CONFIG_IEEE80211W=y
CONFIG_IEEE80211N=y
CONFIG_WPS=y
CONFIG_FULL_DYNAMIC_VLAN=y
EOF

# 4. Build
echo "[4/6] Compiling..."
make -j$(nproc) 2>&1 | tail -5

# 5. Install
echo "[5/6] Installing to $INSTALL_DIR..."
sudo mkdir -p "$INSTALL_DIR/bin"
sudo cp hostapd "$INSTALL_DIR/bin/hostapd"
sudo cp hostapd_cli "$INSTALL_DIR/bin/hostapd_cli" 2>/dev/null || true

# 6. Verify
echo "[6/6] Verification:"
echo -n "  Version: "
sudo "$INSTALL_DIR/bin/hostapd" -v 2>&1 | head -1
echo "  Path: $INSTALL_DIR/bin/hostapd"

echo ""
echo "=== hostapd 2.6 installed ==="
echo "Binary: $INSTALL_DIR/bin/hostapd"
echo "System hostapd remains at: $(which hostapd)"
