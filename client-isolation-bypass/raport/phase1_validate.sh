#!/bin/bash
# Phase 1: Quick Validation Script
# Executed on Kali VM via SSH

echo "=== PHASE 1: QUICK VALIDATION ==="
echo ""

echo "--- Kernel version ---"
uname -r
echo ""

echo "--- CERTIFICATION_ONUS status ---"
KERNEL_VER=$(uname -r)
grep -E "CERTIFICATION_ONUS|CONFIG_CFG80211=" /boot/config-${KERNEL_VER}
echo ""

echo "--- Wireless modules loaded ---"
lsmod | grep -E "cfg80211|mac80211_hwsim|mac80211"
echo ""

echo "--- hostapd version ---"
hostapd -v 2>&1 | head -1
echo ""

echo "--- GCC version (kernel) ---"
cat /proc/version | grep -oP 'gcc-\d+'
echo ""

echo "--- GCC version (system) ---"
gcc --version 2>/dev/null | head -1 || echo "gcc not installed"
echo ""

echo "--- Available disk space ---"
df -h / | tail -1
echo ""

echo "--- hwsim interfaces ---"
ip link show 2>/dev/null | grep -E "^[0-9]+: (wlan|hwsim)" || echo "No hwsim interfaces loaded"
echo ""

echo "=== PHASE 1 COMPLETE ==="
