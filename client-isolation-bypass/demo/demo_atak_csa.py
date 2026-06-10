#!/usr/bin/env python3
"""
DEMO: Beacon CSA Injection PMF bypass
====================================

Terminal-safe guided wrapper around raport/direct_hwsim_csa.py.
Run on the Kali VM:
    sudo python3 /mnt/hgfs/demo/demo_atak_csa.py
    sudo python3 /tmp/demo_atak_csa.py --yes
"""

import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)


DEFAULT_HOSTAPD = "2.10"
DEFAULT_PMF = 2
DEFAULT_EVIL_CHANNEL = 11
DEFAULT_BEACON_COUNT = 50
DEFAULT_WAIT = 15
DEFAULT_RETRIES = 3


def header(title):
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)
    print()


def info(text):
    print(f"[*] {text}")


def ok(text):
    print(f"[OK] {text}")


def fail(text):
    print(f"[!] {text}")


def pause(enabled):
    if not enabled:
        return
    try:
        input("\n---------- Nacisnij ENTER ----------")
    except EOFError:
        print()


def sanitize(line):
    """Keep line-buffer friendly output while preserving UTF-8 symbols."""
    return line.rstrip("\r\n")


def running_as_root():
    return hasattr(os, "geteuid") and os.geteuid() == 0


def candidate_roots(script_path):
    roots = []
    for parent in [script_path.parent, *script_path.parents]:
        roots.append(parent)
        roots.append(parent.parent)

    env_root = os.environ.get("PMF_BYPASS_ROOT")
    if env_root:
        roots.insert(0, Path(env_root))

    roots.extend([
        Path.cwd(),
        Path("/mnt/hgfs"),
        Path("/mnt/hgfs/client-isolation-bypass"),
        Path.home() / "client-isolation-bypass",
    ])

    seen = set()
    for root in roots:
        try:
            resolved = root.resolve()
        except OSError:
            resolved = root
        if resolved in seen:
            continue
        seen.add(resolved)
        yield resolved


def find_direct_script(override):
    if override:
        path = Path(override).expanduser()
        return path if path.exists() else None

    script_path = Path(__file__).resolve()
    for root in candidate_roots(script_path):
        candidate = root / "raport" / "direct_hwsim_csa.py"
        if candidate.exists():
            return candidate
    return None


def build_direct_cmd(args, direct_script):
    cmd = ["python3", str(direct_script)]
    if not running_as_root():
        cmd.insert(0, "sudo")

    cmd.extend([
        "--hostapd-ver", args.hostapd_ver,
        "--pmf", str(args.pmf),
        "--evil-channel", str(args.evil_channel),
        "--beacon-count", str(args.beacon_count),
        "--wait", str(args.wait),
        "--retries", str(args.retries),
    ])

    if args.no_wmediumd:
        cmd.append("--no-wmediumd")

    return cmd


def fallback_cleanup():
    """Best-effort lab cleanup if the wrapped direct script is interrupted."""
    cleanup_cmds = [
        ["sudo", "pkill", "-x", "hostapd"],
        ["sudo", "pkill", "-f", "^/sbin/wpa_supplicant -i wlan"],
        ["sudo", "pkill", "-x", "tcpdump"],
        ["sudo", "pkill", "-x", "wmediumd"],
        ["sudo", "modprobe", "-r", "mac80211_hwsim"],
    ]
    for cmd in cleanup_cmds:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def stream_command(cmd):
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
        start_new_session=True,
    )
    stopping_child = False

    def terminate_child():
        nonlocal stopping_child
        stopping_child = True
        try:
            proc.kill()
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass

    def stop_child(_signum, _frame):
        if stopping_child:
            return
        fail("Przerwano demo, zatrzymuje test bezposredni...")
        terminate_child()
        fallback_cleanup()

    old_int = signal.signal(signal.SIGINT, stop_child)
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            cleaned = sanitize(line)
            print(f"[direct] {cleaned}")
        return proc.wait()
    finally:
        signal.signal(signal.SIGINT, old_int)


def explain_intro(args):
    header("DEMO: PMF Bypass przez Beacon CSA Injection")
    print("Scenariusz pokazuje obejscie PMF (802.11w) przez Beacon CSA.")
    print("PMF chroni ramki robust management, np. Deauth i Disassoc.")
    print("Beacon pozostaje ramka non-robust, wiec klient nadal przetwarza CSA IE.")
    print()
    print("Atak wysyla falszywe Beacony z Channel Switch Announcement.")
    print("Stacja zmienia kanal z 6 na 11, mimo PMF=2.")
    print("Evil Twin czeka na kanale 11 i obserwujemy reassocjacje klienta.")
    print()
    print("Parametry:")
    print(f"  hostapd:       {args.hostapd_ver}")
    print(f"  PMF:           {args.pmf}")
    print(f"  Evil channel:  {args.evil_channel}")
    print(f"  Beacon count:  {args.beacon_count}")
    print(f"  Retries:       {args.retries}")
    print(f"  wmediumd:      {'OFF' if args.no_wmediumd else 'ON'}")


def explain_attack():
    header("Co pokazuje demo")
    print("1. Legalny AP startuje z PMF=2 na kanale 6.")
    print("2. Stacja laczy sie normalnie przez WPA2/PMF.")
    print("3. Evil Twin czeka na kanale 11.")
    print("4. Interfejs monitor wysyla Beacon z CSA IE tag 37.")
    print("5. Stacja przetwarza Beacon, bo PMF nie chroni Beaconow.")
    print("6. Po zmianie kanalu test symuluje izolacje fizycznego medium.")
    print("7. Stacja probuje ponownie znalezc SSID i moze wejsc w Evil Twin.")
    print()
    print("Oczekiwany dowod: SUCCESS, kanal 11, reassocjacja i log direct_csa_*.")


def print_result(rc):
    header("Wynik demo")
    if rc == 0:
        ok("Demo zakonczone sukcesem.")
        print("Do screenshotow uzyj terminala z linia SUCCESS oraz logow w raport/logs/.")
        return 0

    fail(f"Demo zakonczylo sie kodem {rc}.")
    print("Sprawdz ostatnie linie powyzej oraz logi:")
    print("  /tmp/direct_hwsim_csa/")
    print("  /mnt/hgfs/raport/logs/")
    return rc


def parse_args():
    parser = argparse.ArgumentParser(
        description="Terminal-safe demo wrapper for Beacon CSA PMF bypass."
    )
    parser.add_argument("--hostapd-ver", default=DEFAULT_HOSTAPD, choices=["2.6", "2.10"])
    parser.add_argument("--pmf", type=int, default=DEFAULT_PMF, choices=[0, 1, 2])
    parser.add_argument("--evil-channel", type=int, default=DEFAULT_EVIL_CHANNEL)
    parser.add_argument("--beacon-count", type=int, default=DEFAULT_BEACON_COUNT)
    parser.add_argument("--wait", type=int, default=DEFAULT_WAIT)
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument("--no-wmediumd", action="store_true", default=True)
    parser.add_argument("--with-wmediumd", action="store_false", dest="no_wmediumd")
    parser.add_argument("--direct-script", help="Path to raport/direct_hwsim_csa.py")
    parser.add_argument("--yes", action="store_true", help="Do not pause between sections")
    return parser.parse_args()


def main():
    args = parse_args()
    interactive = not args.yes

    explain_intro(args)
    pause(interactive)
    explain_attack()
    pause(interactive)

    direct_script = find_direct_script(args.direct_script)
    if not direct_script:
        fail("Nie znaleziono raport/direct_hwsim_csa.py.")
        print("Uruchom z repo lub podaj:")
        print("  --direct-script /mnt/hgfs/raport/direct_hwsim_csa.py")
        print("Mozesz tez ustawic PMF_BYPASS_ROOT=/mnt/hgfs.")
        return 2

    header("Start testu bezposredniego")
    ok(f"Direct script: {direct_script}")
    cmd = build_direct_cmd(args, direct_script)
    print("Komenda:")
    print("  " + " ".join(cmd))
    print()

    rc = stream_command(cmd)
    return print_result(rc)


if __name__ == "__main__":
    sys.exit(main())
