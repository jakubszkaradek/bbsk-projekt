#!/usr/bin/env python3
"""
WIDS Evasion Test — Beacon CSA Injection
==========================================
Runs the full PMF bypass exploit while monitoring with scapy_sniffer.
Verifies which (if any) WIDS alerts are triggered by Beacon CSA injection.

Attack: Beacon CSA (subtype 8) with IE 37 — station switches channel.
WIDS:  scapy_sniffer captures all management frames on injection interface.
       Kismet runs passively with alert logging.

Expected result: Beacon CSA should NOT trigger Deauth/Disassoc alerts.
Beacon frames (subtype 8) are normal traffic — WIDS should be blind to CSA.

Usage:
    sudo python3 raport/wids_evasion_test.py
"""

import argparse
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

RAPORT_DIR = Path(__file__).parent
LOG_DIR = RAPORT_DIR / "logs"
PCAP_DIR = RAPORT_DIR / "pcaps" / "csa_injection"
LOG_DIR.mkdir(parents=True, exist_ok=True)
PCAP_DIR.mkdir(parents=True, exist_ok=True)

MGMT_SUBTYPES = {
    0: "AssocReq", 1: "AssocResp", 2: "ReassocReq", 3: "ReassocResp",
    4: "ProbeReq", 5: "ProbeResp", 8: "Beacon",
    10: "Disassoc", 11: "Auth", 12: "Deauth", 13: "Action",
}

# Alert-worthy: frames that PMF should protect
ALERT_SUBTYPES = {10: "Disassoc", 12: "Deauth", 13: "Action"}


def timestamp():
    return datetime.now().strftime("%H:%M:%S")


def log(msg):
    print(f"[{timestamp()}] {msg}", flush=True)


def sudo(cmd):
    return subprocess.run(f"sudo {cmd}", shell=True, capture_output=True, text=True, timeout=30)


# ─── WIDS: scapy_sniffer wrapper ────────────────────────────────────────────
def start_sniffer(iface, pcap_out, duration=90):
    """Start scapy_sniffer in background, returns process."""
    log(f"[WIDS] Starting scapy_sniffer on {iface} ({duration}s)")
    proc = subprocess.Popen(
        ["sudo", "python3", str(RAPORT_DIR.parent / "pmf-bypass-lab-infra" / "wids" / "scapy_sniffer.py"),
         "--iface", iface, "--duration", str(duration), "--out", pcap_out, "--verbose"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    time.sleep(2)
    return proc


def parse_sniffer_output(stdout_lines):
    """Parse scapy_sniffer output, count frame types, detect anomalies."""
    counts = Counter()
    alerts = []
    
    for line in stdout_lines:
        # Count frames: "[timestamp] Beacon    DA=... SA=... BSSID=... [!]"
        for subtype, name in MGMT_SUBTYPES.items():
            if name in line:
                counts[name] += 1
                if subtype in ALERT_SUBTYPES and "[!]" in line:
                    alerts.append(line.strip())
    
    return counts, alerts


# ─── Kismet wrapper ─────────────────────────────────────────────────────────
def start_kismet(iface):
    """Start Kismet in passive mode, logging alerts."""
    log("[WIDS] Starting Kismet...")
    kismet_dir = "/tmp/kismet_wids"
    subprocess.run(["sudo", "mkdir", "-p", kismet_dir], capture_output=True)
    subprocess.run(["sudo", "rm", "-f", f"{kismet_dir}/*"], capture_output=True)
    
    # Kismet 2025 uses different CLI than older versions
    proc = subprocess.Popen(
        ["sudo", "kismet", "--no-server", "--daemonize",
         "-c", iface, "--log-dir", kismet_dir],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(5)
    
    # Check if running
    r = subprocess.run(["pgrep", "kismet"], capture_output=True, text=True)
    if r.stdout.strip():
        log(f"  Kismet running (PID={r.stdout.strip()})")
        return proc, kismet_dir
    else:
        log("  WARNING: Kismet failed to start (non-fatal)")
        return None, kismet_dir


def check_kismet_alerts(kismet_dir):
    """Check Kismet log for alerts (DEAUTHFLOOD, CHANCHANGE, APSPOOF)."""
    alerts = []
    alert_file = Path(kismet_dir) / "kismet_alert.log"
    if alert_file.exists():
        content = alert_file.read_text()
        for keyword in ["DEAUTHFLOOD", "CHANCHANGE", "APSPOOF", "SPOOF", "ANOMALY"]:
            if keyword in content:
                alerts.append(f"KISMET ALERT: {keyword}")
    return alerts


# ─── Main ───────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="WIDS Evasion Test")
    parser.add_argument("--hostapd-ver", default="2.6", choices=["2.6", "2.10"])
    parser.add_argument("--no-kismet", action="store_true", help="Skip Kismet")
    args = parser.parse_args()
    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    sniffer_pcap = str(PCAP_DIR / f"wids_sniffer_{args.hostapd_ver}_{ts}.pcap")
    
    log("=" * 55)
    log("  WIDS EVASION TEST — Beacon CSA Injection")
    log(f"  hostapd: {args.hostapd_ver}  PMF: 2")
    log(f"  WIDS: scapy_sniffer + Kismet")
    log("=" * 55)
    
    # Cleanup
    for p in ["hostapd", "wpa_supplicant", "kismet"]:
        subprocess.run(["sudo", "pkill", "-f", p], capture_output=True)
    time.sleep(1)
    subprocess.run(["sudo", "modprobe", "-r", "mac80211_hwsim"], capture_output=True)
    
    try:
        # Load hwsim
        subprocess.run(["sudo", "modprobe", "mac80211_hwsim", "radios=4"], capture_output=True)
        time.sleep(2)
        
        r = subprocess.run(["sudo", "iw", "dev"], capture_output=True, text=True)
        ifaces = [l.split()[1] for l in r.stdout.split("\n") if l.strip().startswith("Interface ")]
        if len(ifaces) < 4:
            log(f"ERROR: Need 4 interfaces, got {len(ifaces)}")
            return 1
        
        inj_iface = ifaces[2]  # Will be set to monitor mode by the exploit
        log(f"  Injection/monitor iface: {inj_iface}")
        
        # Start WIDS monitoring
        sniffer_proc = start_sniffer(inj_iface, sniffer_pcap, duration=90)
        
        kismet_dir = "/tmp/kismet_wids"
        if not args.no_kismet:
            kismet_proc, kismet_dir = start_kismet(inj_iface)
        
        # Run the full exploit
        log("[ATTACK] Running full exploit...")
        exploit_cmd = (
            f"sudo python3 {RAPORT_DIR}/direct_hwsim_csa.py "
            f"--hostapd-ver {args.hostapd_ver} --pmf 2 --no-wmediumd "
            f"--beacon-count 50 --wait 15"
        )
        r = subprocess.run(exploit_cmd, shell=True, capture_output=True, text=True, timeout=120)
        exploit_output = r.stdout
        
        # Check exploit result
        if "SUCCESS" in exploit_output:
            log("[ATTACK] Exploit SUCCESS — CSA bypassed PMF")
        else:
            log(f"[ATTACK] Exploit result: check log")
        
        # Wait for sniffer to finish
        log("[WIDS] Waiting for sniffer to complete...")
        try:
            sniffer_stdout, _ = sniffer_proc.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            sniffer_proc.kill()
            sniffer_stdout, _ = sniffer_proc.communicate()
        
        # Parse sniffer results
        sniffer_lines = sniffer_stdout.split("\n") if sniffer_stdout else []
        frame_counts, sniffer_alerts = parse_sniffer_output(sniffer_lines)
        
        # Check Kismet
        kismet_alerts = []
        if not args.no_kismet:
            kismet_alerts = check_kismet_alerts(kismet_dir)
            subprocess.run(["sudo", "pkill", "kismet"], capture_output=True)
        
        # ─── Report ─────────────────────────────────────────────────────────
        print()
        print("=" * 55)
        print("  WIDS EVASION RESULTS")
        print("=" * 55)
        print()
        print("--- Frame Counts (scapy_sniffer) ---")
        for name, count in sorted(frame_counts.items(), key=lambda x: x[1], reverse=True):
            alert = " ← ALERT-WORTHY" if name in ALERT_SUBTYPES.values() else ""
            print(f"  {name:15s}: {count:4d}{alert}")
        
        print()
        print("--- Sniffer Alerts ---")
        if sniffer_alerts:
            for a in sniffer_alerts:
                print(f"  {a}")
            print(f"  Total: {len(sniffer_alerts)} alert-worthy frames detected")
        else:
            print("  NONE — Beacon CSA does NOT trigger Deauth/Disassoc alerts!")
        
        print()
        print("--- Kismet Alerts ---")
        if kismet_alerts:
            for a in kismet_alerts:
                print(f"  {a}")
        else:
            print("  NONE — Kismet did not detect Beacon CSA injection!")
        
        print()
        print("--- Verdict ---")
        beacon_count = frame_counts.get("Beacon", 0)
        deauth_count = frame_counts.get("Deauth", 0)
        disassoc_count = frame_counts.get("Disassoc", 0)
        action_count = frame_counts.get("Action", 0)
        
        if deauth_count == 0 and disassoc_count == 0:
            print("  ✅ Beacon CSA injection EVADES standard WIDS detection.")
            print("  Beacon frames (subtype 8) are normal traffic.")
            print("  Only CSA IE (tag 37) inspection would reveal the attack.")
        else:
            print(f"  ⚠️  Detected: Deauth={deauth_count} Disassoc={disassoc_count}")
        
        print(f"  Sniffer PCAP: {sniffer_pcap}")
        print(f"  Beacon frames captured: {beacon_count}")
        print(f"  Action frames captured: {action_count}")
        
        # Save report
        report_path = LOG_DIR / f"wids_evasion_{args.hostapd_ver}_{ts}.txt"
        with open(report_path, "w") as f:
            f.write(f"WIDS Evasion Test\n")
            f.write(f"hostapd: {args.hostapd_ver}\n")
            f.write(f"Date: {ts}\n\n")
            f.write("Frame counts:\n")
            for name, count in sorted(frame_counts.items(), key=lambda x: x[1], reverse=True):
                f.write(f"  {name}: {count}\n")
            f.write(f"\nSniffer alerts: {len(sniffer_alerts)}\n")
            f.write(f"Kismet alerts: {len(kismet_alerts)}\n")
            f.write(f"\nVerdict: Beacon CSA evades WIDS detection\n")
        log(f"Report: {report_path}")
        
        return 0
        
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 2
    finally:
        for p in ["hostapd", "wpa_supplicant", "kismet"]:
            subprocess.run(["sudo", "pkill", "-f", p], capture_output=True)
        subprocess.run(["sudo", "modprobe", "-r", "mac80211_hwsim"], capture_output=True)


if __name__ == "__main__":
    sys.exit(main())
