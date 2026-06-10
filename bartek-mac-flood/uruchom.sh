#!/bin/bash
# uruchom.sh - przygotowuje srodowisko i startuje demo
# uzycie: sudo bash /home/kali/bbsk-projekt/uruchom.sh

set -e

echo ""
echo "============================================================"
echo "  BBSK - MAC Spoofing + Association Hijacking"
echo "  skrypt startowy"
echo "============================================================"
echo ""

# sprawdz root
if [ "$EUID" -ne 0 ]; then
    echo "  blad: uruchom jako root: sudo bash uruchom.sh"
    exit 1
fi

# --- krok 1: czyszczenie poprzedniej sesji ---
echo "  [1/3] czyszczenie poprzedniej sesji mininet..."
mn -c 2>/dev/null || true
echo "  ok"
echo ""

# --- krok 2: modul wirtualnych kart wifi ---
echo "  [2/3] ladowanie wirtualnych kart wifi"
modprobe mac80211_hwsim radios=4
echo "  ok"
echo ""

# --- krok 3: start topologii ---
echo "  [3/3] uruchamianie topologii..."
echo ""
echo "  po uruchomieniu w CLI mininet-wifi nalezy wpisac:"
echo ""
echo "      sta2 python3 /home/kali/bbsk-projekt/demo.py"
echo ""
echo "============================================================"
echo ""

sleep 2

python3 /home/kali/bbsk-projekt/topology.py
