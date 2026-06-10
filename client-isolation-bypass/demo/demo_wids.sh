#!/bin/bash
# ============================================================
# DEMO: WIDS Evasion - czy WIDS wykrywa Beacon CSA
# ============================================================
# Odpal na VM: sudo ./demo_wids.sh
# Pokazuje ze standardowy WIDS nie wykrywa Beacon CSA
# ============================================================

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

pause() { echo; read -p "Nacisnij ENTER..."; echo; }
header() { echo -e "${CYAN}=== $1 ===${NC}"; echo; }
ok() { echo -e "${GREEN}[OK]${NC} $1"; }
info() { echo -e "${YELLOW}[*]${NC} $1"; }

echo
echo "=============================================="
echo "  DEMO: Czy WIDS wykrywa Beacon CSA"
echo "=============================================="
echo
echo "Ten skrypt pokazuje ze standardowy WIDS"
echo "NIE wykrywa ataku Beacon CSA Injection"
echo
echo "WIDS = Wireless Intrusion Detection System"
echo "Monitoruje ramki WiFi i szuka anomalii"
pause

# ---- Co to jest WIDS ----
header "Co monitoruje standardowy WIDS"

echo "Typowy WIDS (np scapy_sniffer, Kismet) szuka:"
echo
echo "  [!] Deauthentication (subtype 12)"
echo "      Atakujacy wysyla sfalszowany Deauth"
echo "      zeby wyrzucic klienta z sieci"
echo "      PMF chroni przed tym jesli wlaczone"
echo
echo "  [!] Disassociation (subtype 10)"
echo "      Podobnie jak Deauth - rozlacza klienta"
echo "      PMF chroni przed tym jesli wlaczone"
echo
echo "  [!] Action Frames (subtype 13)"
echo "      Niektore Action Frames moga byc podejrzane"
echo "      PMF chroni je na hostapd >= 2.7"
echo
echo "  [ ] Beacon (subtype 8)"
echo "      NORMALNY RUCH - kazdy AP wysyla Beacony"
echo "      WIDS NIE flaguje Beaconow jako podejrzane"
echo "      To jest nasza luka"
pause

# ---- Dlaczego Beacon nie jest alertowany ----
header "Dlaczego Beacon (subtype 8) nie jest alertowany"

echo "Beacony to normalny ruch sieci WiFi:"
echo "  - AP wysyla Beacon co ~100ms"
echo "  - Beacon zawiera SSID, kanal, capabilities"
echo "  - Kazda siec WiFi ma tysiace Beaconow na minute"
echo
echo "Gdyby WIDS alertowal na kazdy Beacon:"
echo "  - Bylby zalew falszywych alarmow"
echo "  - Nie daloby sie normalnie korzystac z WiFi"
echo "  - Alarmy bylyby ignorowane (jak bajka o wilku)"
echo
echo "Dlatego WIDS IGNORUJE Beacon jako typ ramki"
echo "To sluszne dla normalnego ruchu"
echo "ALE to wlasnie umozliwia Beacon CSA Injection"
pause

# ---- Porownanie ----
header "Porownanie: Deauth vs Beacon CSA"

echo "Atak Deauth (subtype 12):"
echo "  Wysylasz sfalszowany Deauth"
echo "  PMF go blokuje (jesli wlaczone)"
echo "  WIDS wykrywa (ramka [!])"
echo "  Status: ZABLOKOWANY przez PMF + WYKRYTY przez WIDS"
echo
echo "Atak Beacon CSA (subtype 8):"
echo "  Wysylasz sfalszowany Beacon z CSA IE"
echo "  PMF NIE blokuje (Beacon = non-robust)"
echo "  WIDS NIE wykrywa (Beacon = normalny ruch)"
echo "  Status: PRZECHODZI przez PMF + NIEWYKRYTY przez WIDS"
echo
echo "To podwojna luka:"
echo "  1. PMF nie chroni Beaconow (specyfikacja 802.11w)"
echo "  2. WIDS nie monitoruje Beaconow (za duzo szumu)"
pause

# ---- Co by musialo sie stac ----
header "Co by musial WIDS robic zeby wykryc Beacon CSA"

echo "Zeby wykryc Beacon CSA Injection WIDS musialby:"
echo
echo "  1. Inspekcjonowac CSA Information Element (tag 37)"
echo "     wewnatrz KAZDEGO Beacona"
echo "     To deep packet inspection"
echo
echo "  2. Porownywac CSA z rzeczywista konfiguracja AP"
echo "     Czy AP naprawde zmienia kanal"
echo "     Czy to nie jest sfalszowany Beacon"
echo
echo "  3. Sprawdzac czy wiele Beaconow z tym samym BSSID"
echo "     nie zawiera sprzecznych informacji CSA"
echo
echo "To wymaga CUSTOMOWEGO WIDS"
echo "Zaden standardowy WIDS tego nie robi"
echo "Koszt obliczeniowy bylby znaczacy"
pause

# ---- WNIOSEK ----
header "Wniosek"

echo "Beacon CSA Injection omija ZAROWNO:"
echo
echo "  PMF (802.11w)"
echo "    Beacon = non-robust management frame"
echo "    Specyfikacja nie przewiduje ochrony Beaconow"
echo
echo "  WIDS (scapy_sniffer, Kismet, ...)"
echo "    Beacon = normalny ruch"
echo "    WIDS nie flaguje Beaconow"
echo
echo "To fundamentalna luka w zabezpieczeniach WiFi"
echo "Jedyna obrona: customowy WIDS z deep packet inspection"
echo "albo fizyczne ograniczenia (moc nadawania, RSSI monitoring)"
pause

header "Koniec demo"

echo "Zeby zobaczyc to w praktyce:"
echo "  sudo ./demo_atak_csa.sh"
echo "  (to uruchomi pelny atak z WIDS w tle)"
echo
echo "Sekcja w raporcie:"
echo "  raport/sekcje/06-atak-csa-injection.md (4.6 WIDS EVASION)"
echo
