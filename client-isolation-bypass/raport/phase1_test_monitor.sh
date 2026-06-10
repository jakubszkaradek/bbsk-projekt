#!/bin/bash
# Phase 1: Test Approach D - Monitor interface channel workaround
# FIXED: interface detection

echo "=== APPROACH D: Monitor Interface Channel Workaround ==="

# Load hwsim
echo "[1] Loading mac80211_hwsim..."
modprobe mac80211_hwsim radios=4 2>/dev/null || true
sleep 1

# Find managed interfaces
echo "[2] Interfaces:"
for iface in wlan0 wlan1 wlan2 wlan3; do
    PHY=$(iw dev $iface info 2>/dev/null | grep wiphy | awk '{print $2}')
    TYPE=$(iw dev $iface info 2>/dev/null | grep "type" | awk '{print $2}')
    echo "  $iface: phy=$PHY type=$TYPE"
done

# Use wlan0 as test STA
STA_IFACE="wlan0"
STA_PHY=$(iw dev $STA_IFACE info 2>/dev/null | grep wiphy | awk '{print $2}')
echo ""
echo "[3] Test STA: $STA_IFACE (phy${STA_PHY})"

# Direct channel switch test FIRST (confirmed EOPNOTSUPP)
echo "[4] Direct channel switch test:"
iw dev $STA_IFACE switch channel 11 2>&1
echo ""

# Create monitor interface
echo "[5] Creating mon0 on phy${STA_PHY}..."
iw phy phy${STA_PHY} interface add mon0 type monitor 2>&1
sleep 1

# Set monitor to channel 11
echo "[6] Setting mon0 to channel 11..."
iw dev mon0 set channel 11 2>&1
sleep 1

# Check if STA followed
echo "[7] STA status after mon0 channel change:"
iw dev $STA_IFACE info | grep -E "channel|type|ssid"

# Also check mon0
echo "[8] mon0 status:"
iw dev mon0 info | grep -E "channel|type"

# Try setting STA channel directly while in managed mode
echo "[9] Trying STA channel set while managed:"
iw dev $STA_IFACE set channel 11 2>&1

# Cleanup
echo "[10] Cleanup..."
iw dev mon0 del 2>/dev/null || true
rmmod mac80211_hwsim 2>/dev/null || true

echo ""
echo "=== TEST COMPLETE ==="
