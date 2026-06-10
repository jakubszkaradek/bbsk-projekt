#!/bin/bash
# Extended diag: long wait, full logs, no-PMF test, iw connect test
set -e

echo "=== 1. Load hwsim ==="
sudo modprobe -r mac80211_hwsim 2>/dev/null || true
sleep 1
sudo modprobe mac80211_hwsim radios=4
sleep 2

IFACES=($(iw dev 2>/dev/null | grep -oP 'Interface \K\w+'))
AP_IF="${IFACES[0]}"
STA_IF="${IFACES[1]}"
INJ_IF="${IFACES[2]}"
echo "AP=$AP_IF STA=$STA_IF INJ=$INJ_IF"

sudo ip link set "$AP_IF" up
sudo ip link set "$STA_IF" up

# ---- TEST A: Open network (no wpa_supplicant, direct iw) ----
echo ""
echo "=== TEST A: Open network via iw connect ==="
sudo pkill hostapd 2>/dev/null || true
sleep 0.5
cat > /tmp/hapd_open.conf << HEOF
interface=$AP_IF
driver=nl80211
ssid=CSATestOpen
hw_mode=g
channel=6
ctrl_interface=/var/run/hostapd
HEOF
sudo hostapd /tmp/hapd_open.conf > /tmp/hapd_open.log 2>&1 &
HAPD_PID=$!
sleep 2
echo "hostapd PID=$HAPD_PID"
sudo iw dev "$AP_IF" info | grep -E "type|ssid"

# Direct connect using iw
echo "Connecting via iw..."
sudo iw dev "$STA_IF" connect CSATestOpen 2437 2>&1 || true
sleep 5
echo "iw link result:"
sudo iw dev "$STA_IF" link
sudo iw dev "$STA_IF" info | grep -E "type|channel|ssid"

sudo kill $HAPD_PID 2>/dev/null || true
sleep 1

# ---- TEST B: WPA2-PSK with PMF=0 ----
echo ""
echo "=== TEST B: WPA2-PSK, PMF=0 ==="
sudo pkill hostapd 2>/dev/null || true
sudo pkill wpa_supplicant 2>/dev/null || true
sleep 1

cat > /tmp/hapd_psk.conf << HEOF
interface=$AP_IF
driver=nl80211
ssid=CSATestPSK
hw_mode=g
channel=6
wpa=2
wpa_passphrase=TestPass123
wpa_key_mgmt=WPA-PSK
wpa_pairwise=CCMP
rsn_pairwise=CCMP
ieee80211w=0
beacon_int=100
ctrl_interface=/var/run/hostapd
HEOF
sudo hostapd /tmp/hapd_psk.conf > /tmp/hapd_psk.log 2>&1 &
HAPD_PID=$!
sleep 2
echo "hostapd PID=$HAPD_PID (PMF=0)"
sudo iw dev "$AP_IF" info | grep -E "type|ssid"

cat > /tmp/wpa_psk.conf << WEOF
ctrl_interface=/var/run/wpa_supplicant
update_config=1
network={
    ssid="CSATestPSK"
    psk="TestPass123"
    key_mgmt=WPA-PSK
    pairwise=CCMP
    group=CCMP
    ieee80211w=0
}
WEOF
sudo wpa_supplicant -i "$STA_IF" -c /tmp/wpa_psk.conf -D nl80211 > /tmp/wpa_psk.log 2>&1 &
WPAS_PID=$!

echo "Waiting 20s for association..."
for i in $(seq 1 20); do
    RESULT=$(sudo iw dev "$STA_IF" link 2>&1)
    if echo "$RESULT" | grep -q "Connected to"; then
        echo "ASSOCIATED after ${i}s!"
        echo "$RESULT"
        break
    fi
    sleep 1
done
if ! echo "$RESULT" | grep -q "Connected to"; then
    echo "Not associated after 20s"
fi

echo "=== wpa_supplicant FULL LOG ==="
cat /tmp/wpa_psk.log

echo "=== hostapd LOG ==="
cat /tmp/hapd_psk.log

sudo kill $HAPD_PID 2>/dev/null || true
sudo kill $WPAS_PID 2>/dev/null || true
sleep 1

# ---- TEST C: WPA2-PSK with PMF=2 ----
echo ""
echo "=== TEST C: WPA2-PSK, PMF=2 ==="
sudo pkill hostapd 2>/dev/null || true
sudo pkill wpa_supplicant 2>/dev/null || true
sleep 1

cat > /tmp/hapd_pmf2.conf << HEOF
interface=$AP_IF
driver=nl80211
ssid=CSATestPMF2
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
logger_stdout=-1
logger_stdout_level=2
HEOF
sudo hostapd /tmp/hapd_pmf2.conf > /tmp/hapd_pmf2.log 2>&1 &
HAPD_PID=$!
sleep 2

cat > /tmp/wpa_pmf2.conf << WEOF
ctrl_interface=/var/run/wpa_supplicant
update_config=1
country=PL
network={
    ssid="CSATestPMF2"
    psk="TestPass123"
    proto=RSN
    key_mgmt=WPA-PSK
    pairwise=CCMP
    group=CCMP
    ieee80211w=2
}
WEOF
sudo wpa_supplicant -i "$STA_IF" -c /tmp/wpa_pmf2.conf -D nl80211 > /tmp/wpa_pmf2.log 2>&1 &
WPAS_PID=$!

echo "Waiting 25s for association..."
for i in $(seq 1 25); do
    RESULT=$(sudo iw dev "$STA_IF" link 2>&1)
    if echo "$RESULT" | grep -q "Connected to"; then
        echo "ASSOCIATED after ${i}s!"
        echo "$RESULT"
        break
    fi
    sleep 1
done
if ! echo "$RESULT" | grep -q "Connected to"; then
    echo "Not associated after 25s"
fi

echo "=== wpa_supplicant FULL LOG ==="
cat /tmp/wpa_pmf2.log

echo "=== hostapd LOG ==="
cat /tmp/hapd_pmf2.log

echo "=== STA info ==="
sudo iw dev "$STA_IF" info | grep -E "type|channel|ssid"

sudo kill $HAPD_PID 2>/dev/null || true
sudo kill $WPAS_PID 2>/dev/null || true
sudo modprobe -r mac80211_hwsim 2>/dev/null || true
echo "DONE"