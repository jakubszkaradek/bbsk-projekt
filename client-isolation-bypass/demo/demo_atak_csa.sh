#!/bin/bash
# Terminal-safe launcher for demo_atak_csa.py.
# The Python wrapper calls raport/direct_hwsim_csa.py, which is the source of truth.

set -u

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

find_demo() {
    for candidate in \
        "$script_dir/demo_atak_csa.py" \
        "/mnt/hgfs/demo/demo_atak_csa.py" \
        "$HOME/client-isolation-bypass/demo/demo_atak_csa.py"
    do
        if [ -f "$candidate" ]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

demo_py="$(find_demo || true)"
if [ -z "$demo_py" ]; then
    echo "[!] Nie znaleziono demo_atak_csa.py"
    echo "Uruchom z repo albo podaj bezposrednio:"
    echo "  sudo python3 /mnt/hgfs/demo/demo_atak_csa.py"
    exit 2
fi

echo "============================================================"
echo "DEMO: PMF Bypass przez Beacon CSA Injection"
echo "============================================================"
echo
echo "[*] Launcher: $demo_py"
echo "[*] Logika ataku: raport/direct_hwsim_csa.py"
echo

if [ "$(id -u)" -eq 0 ]; then
    exec python3 "$demo_py" "$@"
else
    exec sudo python3 "$demo_py" "$@"
fi
