#!/usr/bin/env python3
"""
Management Frame Sniffer (Scapy-based WIDS component)

Captures management frames on a monitor interface, classifies them by type,
and logs with timestamps for Wireshark analysis.

Monitored frame types:
    - Deauthentication (subtype 12)
    - Disassociation (subtype 10)
    - Action Frames (subtype 13) — includes CSA, BSS Transition
    - Beacon (subtype 8)
    - Probe Request/Response (subtypes 4, 5)
    - Authentication (subtype 11)

Output:
    - console_summary: human-readable summary of captured frames
    - output.pcap: full packet capture for Wireshark analysis

Usage:
    sudo python3 scapy_sniffer.py --iface <monitor_interface> [--duration 60] [--out captured.pcap]
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

# Management frame subtype → name mapping
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

# Frames of primary interest for PMF analysis
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
    """Return ISO 8601 timestamp."""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


class FrameLogger:
    """Tracks and logs captured management frames."""

    def __init__(self, verbose=False):
        self.packets = []
        self.counts = Counter()
        self.verbose = verbose

    def log_frame(self, packet):
        """Process a single captured packet."""
        if not packet.haslayer(Dot11):
            return

        dot11 = packet[Dot11]
        subtype = dot11.subtype

        if subtype not in MGMT_SUBTYPES:
            return  # Not a management frame

        self.packets.append(packet)
        self.counts[subtype] += 1

        if self.verbose or subtype in INTEREST_SUBTYPES:
            self._print_frame(subtype, dot11)

    def _print_frame(self, subtype, dot11):
        """Print a single frame summary."""
        frame_name = MGMT_SUBTYPES.get(subtype, f"Unknown({subtype})")
        addr1 = dot11.addr1 or "—"
        addr2 = dot11.addr2 or "—"
        addr3 = dot11.addr3 or "—"

        # Mark frames of interest
        marker = " [!]" if subtype in INTEREST_SUBTYPES else ""

        print(f"[{timestamp()}] {frame_name:25s} "
              f"DA={addr1}  SA={addr2}  BSSID={addr3}{marker}")

    def print_summary(self):
        """Print capture summary statistics."""
        print(f"\n{'='*65}")
        print(f"Capture Summary ({len(self.packets)} management frames)")
        print(f"{'='*65}")
        for subtype, name in sorted(MGMT_SUBTYPES.items()):
            count = self.counts.get(subtype, 0)
            if count > 0:
                interest = " ← PMF-RELEVANT" if subtype in INTEREST_SUBTYPES else ""
                print(f"  {name:25s} : {count:5d}{interest}")
        print(f"{'='*65}\n")


def main():
    args = parse_args()

    logger = FrameLogger(verbose=args.verbose)

    print(f"[{timestamp()}] Starting capture on {args.iface}")
    print(f"[{timestamp()}] Duration: {args.duration}s")
    print(f"[{timestamp()}] Output: {args.out}")
    print(f"[{timestamp()}] Monitoring: Deauth, Disassoc, Action, Beacon")
    print(f"{'─'*65}")

    try:
        sniff(
            iface=args.iface,
            prn=logger.log_frame,
            timeout=args.duration,
            store=0,  # Don't store in scapy's internal buffer
        )
    except KeyboardInterrupt:
        print(f"\n[{timestamp()}] Capture interrupted by user")
    except PermissionError:
        print("ERROR: Permission denied. Run with sudo.", file=sys.stderr)
        sys.exit(1)

    # Save to PCAP
    if logger.packets:
        wrpcap(args.out, logger.packets)
        print(f"[{timestamp()}] Saved {len(logger.packets)} packets to {args.out}")

    logger.print_summary()


if __name__ == "__main__":
    main()
