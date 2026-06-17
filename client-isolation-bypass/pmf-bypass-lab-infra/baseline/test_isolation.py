#!/usr/bin/env python3
"""
test bazowy: weryfikacja client isolation
sprawdza czy ap poprawnie blokuje ruch l2 miedzy stacjami
z ap_isolate=1 ping miedzy sta1 a sta2 powinien miec 100% strat
"""

import os
import sys
import time
import argparse

from mn_wifi.net import Mininet_wifi
from mn_wifi.cli import CLI
from mininet.log import setLogLevel, info


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOSTAPD_CONF = os.path.join(BASE_DIR, "configs", "hostapd.conf")
WPA_CONF = os.path.join(BASE_DIR, "configs", "wpa_supplicant.conf")


def run_test():
    """uruchamia test client isolation"""
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
    sta3 = net.addStation("sta3", wpas_params=["-c", WPA_CONF])

    net.setPropagationModel(model="logDistance", exp=3.5)
    net.configureNodes()

    net.addLink(ap1, sta1)
    net.addLink(ap1, sta2)
    net.addLink(ap1, sta3)

    net.start()
    info("\n*** Waiting for association...\n")
    time.sleep(15)

    # weryfikacja ip
    info("=== IP Address Assignment ===\n")
    for sta in [sta1, sta2, sta3]:
        ip = sta.IP()
        info(f"  {sta.name}: {ip}\n")

    # test: ping sta1 -> sta2
    sta2_ip = sta2.IP()
    info(f"\n=== PING Test: {sta1.name} -> {sta2.name} ({sta2_ip}) ===\n")

    # 5 pingow, timeout 2s
    result = sta1.cmd(f"ping -c 5 -W 2 {sta2_ip}")
    info(result)

    # analiza wyniku
    if "100% packet loss" in result or "0 received" in result or "Network is unreachable" in result:
        info("\n[PASS] Client Isolation working correctly.\n")
        info("       Direct L2 communication between stations is BLOCKED.\n")
        test_passed = True
    else:
        info("\n[FAIL] Client Isolation NOT enforced!\n")
        info("       Stations can communicate directly - isolation is broken.\n")
        test_passed = False

    # opcjonalnie: test arp z sta3
    info(f"\n=== ARP Test: {sta3.name} attempting ARP for {sta1.name} ===\n")
    arp_result = sta3.cmd(f"arping -c 3 -I wlan0 {sta1.IP()}")
    info(arp_result)

    if "0 response" in arp_result or "100% unanswered" in arp_result:
        info("[PASS] ARP isolation confirmed.\n")
    else:
        info("[FAIL] ARP isolation broken.\n")

    net.stop()

    return test_passed


if __name__ == "__main__":
    setLogLevel("info")
    passed = run_test()
    sys.exit(0 if passed else 1)
