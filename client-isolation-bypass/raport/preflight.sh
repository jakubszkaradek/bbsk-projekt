#!/bin/bash
# Pre-flight check before running direct_hwsim_csa.py
echo "=== Pre-flight Check ==="

echo "hostapd 2.6:"
/opt/hostapd-2.6/bin/hostapd -v 2>&1 | head -1

echo "wmediumd:"
which wmediumd

echo "scapy:"
python3 -c "from scapy.all import RadioTap; print('OK')" 2>&1

echo "hwsim modules loaded:"
lsmod | grep hwsim || echo "not loaded"

echo "cleanup needed:"
pgrep hostapd && echo "  hostapd running" || echo "  hostapd: clean"
pgrep wpa_supplicant && echo "  wpa_supplicant running" || echo "  wpa_supplicant: clean"
pgrep wmediumd && echo "  wmediumd running" || echo "  wmediumd: clean"

echo "=== Pre-flight DONE ==="
