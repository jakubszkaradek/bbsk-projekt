#!/bin/bash
# Test: does kernel support channel switch on hwsim STA?
set -e
sudo modprobe -r mac80211_hwsim 2>/dev/null || true
sleep 1
sudo modprobe mac80211_hwsim radios=4
sleep 2

IFACES=($(iw dev 2>/dev/null | grep -oP 'Interface \K\w+'))
AP_IF="${IFACES[0]}"
STA_IF="${IFACES[1]}"
echo "AP=$AP_IF STA=$STA_IF"

sudo ip link set "$AP_IF" up
sudo ip link set "$STA_IF" up
sudo pkill hostapd 2>/dev/null || true
sudo pkill wpa_supplicant 2>/dev/null || true
sleep 1
sudo rm -f /var/run/wpa_supplicant/*

cat > /tmp/hapd.conf << HEOF
interface=$AP_IF
driver=nl80211
ssid=CSATest
hw_mode=g
channel=6
wpa=2
wpa_passphrase=TestPass123
wpa_key_mgmt=WPA-PSK
wpa_pairwise=CCMP
rsn_pairwise=CCMP
ieee80211w=2
beacon_int=100
ctrl_interface=/var/run/hostapd
HEOF
sudo hostapd /tmp/hapd.conf > /tmp/hapd.log 2>&1 &
sleep 2

cat > /tmp/wpas.conf << WEOF
ctrl_interface=/var/run/wpa_supplicant
update_config=1
network={
    ssid="CSATest"
    psk="TestPass123"
    key_mgmt=WPA-PSK
    pairwise=CCMP
    group=CCMP
    ieee80211w=2
}
WEOF
sudo wpa_supplicant -i "$STA_IF" -c /tmp/wpas.conf -D nl80211 > /tmp/wpas.log 2>&1 &
sleep 10

echo "=== BEFORE SWITCH ==="
sudo iw dev "$STA_IF" info | grep channel
sudo iw dev "$STA_IF" link | head -3

echo "=== TRY SWITCH TO CH 11 (via iw) ==="
# Try direct channel switch on the connected STA
sudo iw dev "$STA_IF" switch channel 11 2>&1 || true
sleep 3

echo "=== AFTER SWITCH ==="
sudo iw dev "$STA_IF" info | grep channel
sudo iw dev "$STA_IF" link | head -3

echo "=== TRY SET CHANNEL directly ==="
sudo iw dev "$STA_IF" set channel 11 2>&1 || true
sleep 2
sudo iw dev "$STA_IF" info | grep channel

echo "=== CHECK CONFIG_CFG80211_CERTIFICATION_ONUS ==="
zcat /proc/config.gz 2>/dev/null | grep CFG80211_CERTIFICATION || echo "config.gz not available"
grep CFG80211_CERTIFICATION /boot/config-* 2>/dev/null | head -1 || echo "not in /boot"

sudo pkill hostapd 2>/dev/null || true
sudo pkill wpa_supplicant 2>/dev/null || true
sudo modprobe -r mac80211_hwsim 2>/dev/null || true
echo "DONE"