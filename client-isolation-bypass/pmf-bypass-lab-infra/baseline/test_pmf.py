#!/usr/bin/env python3
"""
Baseline Test: PMF (802.11w) Protection Verification

Tests whether the AP correctly protects Robust Management Frames.

Test 1 — Deauth Spoofing:
    Attempt to send a spoofed deauthentication frame from outside the network.
    With PMF=required (ieee80211w=2), the client should IGNORE unprotected deauth
    frames and remain connected.

Expected result:
    - Spoofed (unprotected) deauth frame is REJECTED by station
    - Station remains associated with the AP
    - PMF protection verified

Usage:
    sudo python3 test_pmf.py
"""

import os
import sys
import time

from mn_wifi.net import Mininet_wifi
from mininet.log import setLogLevel, info


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOSTAPD_CONF = os.path.join(BASE_DIR, "configs", "hostapd.conf")
WPA_CONF = os.path.join(BASE_DIR, "configs", "wpa_supplicant.conf")


def check_association(sta):
    """Check if station is associated with AP."""
    result = sta.cmd(f"iw dev wlan0 link")
    return "Not connected" not in result


def get_sta_bssid(sta):
    """Extract BSSID (AP MAC) from iw link output."""
    result = sta.cmd(f"iw dev wlan0 link")
    for line in result.split("\n"):
        if "Connected to" in line:
            return line.split()[-1].strip()
    return None


def run_test():
    """Run PMF baseline verification test."""
    net = Mininet_wifi()

    info("*** Creating nodes\n")

    ap1 = net.addAccessPoint(
        "ap1",
        ssid="PMF_Lab_Secure",
        mode="g",
        channel="6",
        failMode="standalone",
        hostapd_params=["-f", HOSTAPD_CONF],
    )

    sta1 = net.addStation("sta1", wpas_params=["-c", WPA_CONF])
    sta2 = net.addStation("sta2", wpas_params=["-c", WPA_CONF])

    net.setPropagationModel(model="logDistance", exp=3.5)
    net.configureNodes()

    net.addLink(ap1, sta1)
    net.addLink(ap1, sta2)

    net.start()

    info("\n*** Waiting for association...\n")
    time.sleep(15)

    # ---- Pre-test: verify association ----
    info("=== Pre-Test Association Check ===\n")
    if check_association(sta1):
        info(f"  {sta1.name}: ASSOCIATED\n")
        ap_bssid = get_sta_bssid(sta1)
        info(f"  AP BSSID: {ap_bssid}\n")
    else:
        info(f"  {sta1.name}: NOT ASSOCIATED — cannot run PMF test\n")
        net.stop()
        return False

    # ---- Test: Spoofed Deauth Frame ----
    info("=== Test: Sending Spoofed (Unprotected) Deauth Frame ===\n")

    sta1_mac = sta1.wintfs[0].mac
    ap_mac = ap1.wintfs[0].mac

    info(f"  STA MAC:   {sta1_mac}\n")
    info(f"  AP MAC:    {ap_mac}\n")

    # Use scapy via sta1's shell to inject a raw deauth frame
    # This simulates an external attacker who does NOT have the PMF keys
    scapy_cmd = f"""
python3 -c "
from scapy.all import RadioTap, Dot11, Dot11Deauth, sendp
import sys

# Spoofed deauth: pretend to be AP sending deauth to station
frame = RadioTap() / Dot11(
    type=0, subtype=12,   # Management / Deauthentication
    addr1='{sta1_mac}',   # Destination = station
    addr2='{ap_mac}',     # Source = spoofed AP MAC
    addr3='{ap_mac}',     # BSSID
) / Dot11Deauth(reason=7)

# Send on station's interface (simulates attacker injecting from outside)
sendp(frame, iface='wlan0', count=3, inter=0.1, verbose=True)
print('Deauth frames sent.')
"
"""
    result = sta1.cmd(scapy_cmd)
    info(result)

    # --- Wait and check if station is still connected ---
    time.sleep(5)

    info("\n=== Post-Attack Association Check ===\n")
    if check_association(sta1):
        info(f"  {sta1.name}: STILL ASSOCIATED\n")
        info("\n[PASS] PMF protection working.\n")
        info("       Unprotected deauth frame was rejected by station.\n")
        info("       PMF (ieee80211w=2) correctly protects management frames.\n")
        test_passed = True
    else:
        info(f"  {sta1.name}: DISCONNECTED\n")
        info("\n[FAIL] PMF protection FAILED.\n")
        info("       Station disconnected after spoofed deauth.\n")
        info("       PMF may not be properly enforced.\n")
        test_passed = False

    net.stop()
    return test_passed


if __name__ == "__main__":
    setLogLevel("info")
    passed = run_test()
    sys.exit(0 if passed else 1)
