#!/usr/bin/env python3
"""
sniffer ramek zarzadczych (scapy-based wids)
przechwytuje ramki zarzadcze na interfejsie monitor, klasyfikuje po typie
loguje z timestampami do analizy w wireshark
monitorowane: deauth (12), disassoc (10), action (13), beacon (8), probe req/resp (4,5), auth (11)
"""

import argparse
import sys
import time
from collections import Counter
from datetime import datetime

from scapy.all import (
    sniff, wrpcap,
    Dot11, Dot11Deauth, Dot11Disas,
    Dot11Beacon, Dot11ProbeReq, Dot11ProbeResp,
    Dot11Auth, Dot11AssoReq, Dot11AssoResp, Dot11ReassoReq,
    RadioTap,
)

# mapowanie subtype -> nazwa ramki zarzadczej
MGMT_SUBTYPES = {
    0:  "Association Request",
    1:  "Association Response",
    2:  "Reassociation Request",
    3:  "Reassociation Response",
    4:  "Probe Request",
    5:  "Probe Response",
    8:  "Beacon",
    10: "Disassociation",
    11: "Authentication",
    12: "Deauthentication",
    13: "Action",
}

# ramki szczegolnie istotne dla analizy pmf
INTEREST_SUBTYPES = {10, 12, 13, 8}


def parse_args():
    parser = argparse.ArgumentParser(description="Management Frame Sniffer")
    parser.add_argument(
        "--iface", required=True,
        help="Monitor interface (e.g., ap1-mp1, wlan0mon)",
    )
    parser.add_argument(
        "--duration", type=int, default=60,
        help="Capture duration in seconds (default: 60)",
    )
    parser.add_argument(
        "--out", default="captured.pcap",
        help="Output PCAP file (default: captured.pcap)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print every captured frame to stdout",
    )
    return parser.parse_args()


def timestamp():
    """zwraca timestamp iso 8601"""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


class FrameLogger:
    """sledzi i loguje przechwycone ramki zarzadcze"""

    def __init__(self, verbose=False):
        self.packets = []
        self.counts = Counter()
        self.verbose = verbose

    def log_frame(self, packet):
        """przetwarza pojedynczy przechwycony pakiet"""
        if not packet.haslayer(Dot11):
            return

        dot11 = packet[Dot11]
        subtype = dot11.subtype

        if subtype not in MGMT_SUBTYPES:
            return  # nie ramka zarzadcza

        self.packets.append(packet)
        self.counts[subtype] += 1

        if self.verbose or subtype in INTEREST_SUBTYPES:
            self._print_frame(subtype, dot11)

    def _print_frame(self, subtype, dot11):
        """wypisuje podsumowanie ramki"""
        frame_name = MGMT_SUBTYPES.get(subtype, f"Unknown({subtype})")
        addr1 = dot11.addr1 or "-"
        addr2 = dot11.addr2 or "-"
        addr3 = dot11.addr3 or "-"

        # zaznacz ramki istotne dla pmf
        marker = " [!]" if subtype in INTEREST_SUBTYPES else ""

        print(f"[{timestamp()}] {frame_name:25s} "
              f"DA={addr1}  SA={addr2}  BSSID={addr3}{marker}")

    def print_summary(self):
        """wypisuje statystyki przechwytywania"""
        print(f"\n{'='*65}")
        print(f"Capture Summary ({len(self.packets)} management frames)")
        print(f"{'='*65}")
        for subtype, name in sorted(MGMT_SUBTYPES.items()):
            count = self.counts.get(subtype, 0)
            if count > 0:
                interest = " <-- PMF-RELEVANT" if subtype in INTEREST_SUBTYPES else ""
                print(f"  {name:25s} : {count:5d}{interest}")
        print(f"{'='*65}\n")


def main():
    args = parse_args()

    logger = FrameLogger(verbose=args.verbose)

    print(f"[{timestamp()}] Starting capture on {args.iface}")
    print(f"[{timestamp()}] Duration: {args.duration}s")
    print(f"[{timestamp()}] Output: {args.out}")
    print(f"[{timestamp()}] Monitoring: Deauth, Disassoc, Action, Beacon")
    print(f"{'-'*65}")

    try:
        sniff(
            iface=args.iface,
            prn=logger.log_frame,
            timeout=args.duration,
            store=0,  # nie przechowuj w wewnetrznym buforze scapy
        )
    except KeyboardInterrupt:
        print(f"\n[{timestamp()}] Capture interrupted by user")
    except PermissionError:
        print("ERROR: Permission denied. Run with sudo.", file=sys.stderr)
        sys.exit(1)

    # zapis do pcap
    if logger.packets:
        wrpcap(args.out, logger.packets)
        print(f"[{timestamp()}] Saved {len(logger.packets)} packets to {args.out}")

    logger.print_summary()


if __name__ == "__main__":
    main()
