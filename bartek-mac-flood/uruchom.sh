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

# --- krok 1: Open vSwitch ---
echo "  [1/4] uruchamianie Open vSwitch..."
service openvswitch-switch start 2>/dev/null || true
sleep 1
# sprawdz czy dziala
if ! ovs-vsctl show &>/dev/null; then
    echo "  blad: OVS nie odpowiada, probuje jeszcze raz..."
    service openvswitch-switch restart
    sleep 2
fi
echo "  ok"
echo ""

# --- krok 2: czyszczenie poprzedniej sesji ---
echo "  [2/4] czyszczenie poprzedniej sesji mininet..."
mn -c 2>/dev/null || true
echo "  ok"
echo ""

# --- krok 3: modul wirtualnych kart wifi ---
echo "  [3/4] ladowanie wirtualnych kart wifi..."
modprobe mac80211_hwsim radios=4
echo "  ok"
echo ""

# --- krok 4: start topologii ---
echo "  [4/4] uruchamianie topologii..."
echo ""
echo "  po uruchomieniu w CLI mininet-wifi nalezy wpisac:"
echo ""
echo "      sta2 python3 /home/kali/bbsk-projekt/demo.py"
echo ""
echo "============================================================"
echo ""

sleep 2

python3 /home/kali/bbsk-projekt/topology.py
