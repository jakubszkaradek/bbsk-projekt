#!/bin/bash
# Direct hwsim CSA test — bash version
# Runs step-by-step on Kali VM: hostapd + wpa_supplicant on hwsim

set -e

echo "=== 1. Load hwsim ==="
sudo modprobe -r mac80211_hwsim 2>/dev/null || true
sleep 1
sudo modprobe mac80211_hwsim radios=4
sleep 2

# Discover interfaces
IFACES=($(iw dev 2>/dev/null | grep -oP 'Interface \K\w+'))
AP_IF="${IFACES[0]}"
STA_IF="${IFACES[1]}"
echo "AP=$AP_IF STA=$STA_IF (${IFACES[*]})"

echo ""
echo "=== 2. Bring interfaces up ==="
sudo ip link set "$AP_IF" up
sudo ip link set "$STA_IF" up

echo ""
echo "=== 3. Write hostapd config ==="
cat > /tmp/hostapd_test.conf << 'HOSTAPDEOF'
interface=CHANGEME_AP
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
logger_stdout=-1
logger_stdout_level=2
HOSTAPDEOF
sed -i "s/CHANGEME_AP/$AP_IF/" /tmp/hostapd_test.conf

echo ""
echo "=== 4. Start hostapd ==="
sudo pkill hostapd 2>/dev/null || true
sleep 1
sudo hostapd /tmp/hostapd_test.conf > /tmp/hostapd_test.log 2>&1 &
HOSTAPD_PID=$!
sleep 3

echo "hostapd PID=$HOSTAPD_PID"
sudo iw dev "$AP_IF" info | grep -E "type|channel|ssid" || echo "AP info failed"

echo ""
echo "=== 5. Scan for AP ==="
sudo iw dev "$STA_IF" scan 2>&1 | grep -A5 "CSATest" || echo "Scan found no CSATest AP"

echo ""
echo "=== 6. Write wpa_supplicant config ==="
cat > /tmp/wpa_test.conf << WPAEOF
ctrl_interface=/var/run/wpa_supplicant
update_config=1
country=PL
network={
    ssid="CSATest"
    psk="TestPass123"
    proto=RSN
    key_mgmt=WPA-PSK
    pairwise=CCMP
    group=CCMP
    ieee80211w=2
}
WPAEOF

echo ""
echo "=== 7. Start wpa_supplicant ==="
sudo pkill wpa_supplicant 2>/dev/null || true
sleep 1
sudo wpa_supplicant -i "$STA_IF" -c /tmp/wpa_test.conf -D nl80211 > /tmp/wpa_test.log 2>&1 &
WPAS_PID=$!
sleep 2
echo "wpa_supplicant PID=$WPAS_PID"

echo ""
echo "=== 8. Wait for association (15s) ==="
for i in $(seq 1 15); do
    RESULT=$(sudo iw dev "$STA_IF" link 2>&1)
    if echo "$RESULT" | grep -q "Connected to"; then
        echo "ASSOCIATED after ${i}s!"
        echo "$RESULT"
        break
    fi
    sleep 1
done

if ! echo "$RESULT" | grep -q "Connected to"; then
    echo "TIMEOUT: $RESULT"
fi

echo ""
echo "=== 9. STA status ==="
sudo iw dev "$STA_IF" info | grep -E "type|channel|ssid"

echo ""
echo "=== 10. hostapd log (last 30 lines) ==="
tail -30 /tmp/hostapd_test.log 2>/dev/null || echo "no log"

echo ""
echo "=== 11. wpa_supplicant log (last 30 lines) ==="
tail -30 /tmp/wpa_test.log 2>/dev/null || echo "no log"

echo ""
echo "=== 12. Cleanup ==="
sudo kill $HOSTAPD_PID 2>/dev/null || true
sudo kill $WPAS_PID 2>/dev/null || true
sleep 1
sudo pkill hostapd 2>/dev/null || true
sudo pkill wpa_supplicant 2>/dev/null || true
sudo modprobe -r mac80211_hwsim 2>/dev/null || true
echo "Done."