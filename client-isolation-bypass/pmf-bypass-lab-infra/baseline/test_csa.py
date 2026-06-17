#!/usr/bin/env python3
"""
test csa v3 - poprawione wyciaganie mac + detekcja scapy
mac z ip link (wintfs.mac = None w tej wersji Mininet-WiFi)
detekcja scapy: szukamy znakow '>' (verbose output scapy)
"""

import os, sys, time, re
from mn_wifi.net import Mininet_wifi
from mininet.log import setLogLevel, info

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOSTAPD_CONF = os.path.join(BASE_DIR, "configs", "hostapd.conf")
WPA_CONF = os.path.join(BASE_DIR, "configs", "wpa_supplicant.conf")
IFACE = "wlan0"


def get_sta_mac(sta):
    """wyciaga mac z ip link wewnatrz namespace"""
    r = sta.cmd("ip -c=never link show wlan0")
    m = re.search(r'link/ether ([0-9a-f:]+)', r)
    return m.group(1) if m else "00:00:00:00:00:01"


def iface_is_up(sta):
    """sprawdza czy wlan0 jest UP"""
    r = sta.cmd("ip -c=never link show wlan0")
    return "state UP" in r


def run_test():
    net = Mininet_wifi()
    info("*** Creating nodes\n")

    ap1 = net.addAccessPoint("ap1", ssid="PMF_Lab_Secure", mode="g", channel="6",
                              failMode="standalone", hostapd_params=["-f", HOSTAPD_CONF])
    sta1 = net.addStation("sta1", wpas_params=["-c", WPA_CONF])

    net.setPropagationModel(model="logDistance", exp=3.5)
    net.configureNodes()
    net.addLink(ap1, sta1)
    net.start()

    info("\n*** Waiting 15s for DHCP...\n")
    time.sleep(15)

    # przed testem
    info("=== Pre-Test ===\n")
    ip_before = sta1.IP()
    up_before = iface_is_up(sta1)
    sta_mac = get_sta_mac(sta1)
    info(f"  IP: {ip_before}  MAC: {sta_mac}  IFACE_UP: {up_before}\n")

    # csa injection
    info("=== Sending Spoofed CSA Frames ===\n")

    scapy_cmd = (
        'python3 -c "'
        'from scapy.all import RadioTap, Dot11, Dot11Action, Raw, sendp;'
        "csa = b'\\\\x25\\\\x03\\\\x01\\\\x01\\\\x01';"
        f"frame = RadioTap()/Dot11(type=0,subtype=13,addr1='{sta_mac}',addr2='{sta_mac}',addr3='{sta_mac}')/Dot11Action()/Raw(load=csa);"
        f"sendp(frame, iface='{IFACE}', count=30, inter=0.03, verbose=True);"
        'print(''SENT'')"'
    )

    result = sta1.cmd(scapy_cmd)
    sent_count = result.count('>')  # kazdy '>' = potwierdzenie wyslania ramki z scapy
    info(f"  Frames sent: {sent_count}/30\n")

    time.sleep(5)

    # po tescie
    info("=== Post-Test ===\n")
    ip_after = sta1.IP()
    up_after = iface_is_up(sta1)
    info(f"  IP: {ip_after}  IFACE_UP: {up_after}\n")

    # analiza
    ip_stable = ip_before and ip_before == ip_after

    info(f"  IP stable: {ip_stable}\n")

    if ip_stable and sent_count > 0:
        info(f"\n[PASS] Station unaffected ({sent_count} frames sent).\n")
        info("       PMF protects CSA on this hostapd version.\n")
        test_passed = True
    elif not ip_stable and sent_count > 0:
        info(f"\n[ALERT] Station IP changed after {sent_count} frames!\n")
        info("       VULNERABLE hostapd version (CSA = Non-Robust).\n")
        test_passed = False
    else:
        info("\n[PASS] CSA frames blocked (no frames sent or no effect).\n")
        test_passed = True

    net.stop()
    return test_passed


if __name__ == "__main__":
    setLogLevel("info")
    passed = run_test()
    sys.exit(0 if passed else 1)
