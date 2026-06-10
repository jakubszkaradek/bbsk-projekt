#!/bin/bash
# ============================================================
# DEMO: Analiza kernela - dwie sciezki CSA
# ============================================================
# Odpal na VM: ./demo_kernel_analysis.sh
# Pokazuje odkryta architekture dwoch sciezek CSA w kernelu
# ============================================================

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

pause() { echo; read -p "Nacisnij ENTER..."; echo; }
header() { echo -e "${CYAN}=== $1 ===${NC}"; echo; }

echo
echo "=============================================="
echo "  DEMO: Dwie sciezki CSA w kernelu Linux"
echo "=============================================="
echo
echo "Ten skrypt wyjasnia architekture CSA w kernelu"
echo "i dlaczego CERTIFICATION_ONUS nie jest potrzebne"
echo "do ataku Beacon CSA"
echo
echo "Wszystko oparte na analizie kodu zrodlowego 6.19.14"
pause

# ---- Sciezka ADMIN ----
header "Sciezka A: ADMIN (iw dev wlan0 switch channel)"

echo "To jest sciezka uzywana przez komende 'iw'"
echo "Gdy wpisujesz: iw dev wlan0 switch channel 11"
echo
echo "Kod w kernelu: net/wireless/nl80211.c linia 11328"
echo
echo "Funkcja nl80211_channel_switch():"
echo
echo "  switch (dev->ieee80211_ptr->iftype) {"
echo "  case NL80211_IFTYPE_AP:        // dozwolone"
echo "  case NL80211_IFTYPE_P2P_GO:    // dozwolone"
echo "  case NL80211_IFTYPE_ADHOC:     // dozwolone"
echo "  case NL80211_IFTYPE_MESH_POINT: // dozwolone"
echo "  default:                       // STA trafia tutaj"
echo "      return -EOPNOTSUPP;        // -95 blad"
echo "  }"
echo
echo "STA (station) trafia w 'default'"
echo "To HARDCODED blokada - nie ma zwiazku z CERTIFICATION_ONUS"
echo
echo "Dlatego 'iw dev wlan0 switch channel' ZAWSZE zwraca -95"
echo "Niezaleznie od tego czy CERTIFICATION_ONUS jest wlaczone czy nie"
pause

# ---- Sciezka BEACON ----
header "Sciezka B: BEACON CSA (odebranie Beacona z IE 37)"

echo "To jest sciezka uzywana gdy stacja OTRZYMUJE Beacon z CSA"
echo "Beacon przychodzi z AP i zawiera IE tag 37"
echo
echo "Kod w kernelu: net/mac80211/mlme.c linia 2752"
echo
echo "Funkcja ieee80211_sta_process_chanswitch():"
echo
echo "  NIE MA switch(iftype)"
echo "  NIE SPRAWDZA CERTIFICATION_ONUS"
echo "  Sprawdza tylko: CHANCTX_STA_CSA"
echo
echo "hwsim ma te flage ustawiona:"
echo "  drivers/net/wireless/virtual/mac80211_hwsim.c:5587"
echo "  ieee80211_hw_set(hw, CHANCTX_STA_CSA)"
echo
echo "Poniewaz hwsim nie ma callbacku ops->channel_switch"
echo "mac80211 uzywa SCIEZKI PROGRAMOWEJ:"
echo "  timer -> ieee80211_csa_switch_work()"
echo "       -> cfg80211_ch_switch_notify()"
echo
echo "To dziala na STOCKOWYM kernelu Kali"
echo "Bez rekompilacji, bez CERTIFICATION_ONUS"
pause

# ---- Podsumowanie ----
header "Podsumowanie: Dlaczego CERTIFICATION_ONUS NIE JEST POTRZEBNE"

echo "Raporty badawcze z 2026-06-10 blednie zdiagnozowaly problem"
echo "CERTIFICATION_ONUS kontroluje tylko:"
echo "  - REG_RELAX_NO_IR (relaksacja ograniczen kanalow)"
echo "  - REG_CELLULAR_HINTS (regulacje dla stacji bazowych)"
echo "  - podpisywanie regulatory.db"
echo
echo "NIE kontroluje przelaczania kanalow na stacjach"
echo
echo "Sciezka Beacon CSA dziala niezaleznie od tej opcji"
echo "Dowiedzione przez:"
echo "  - analize kodu zrodlowego kernela 6.19.14"
echo "  - testy na hostapd 2.6 i 2.10 z PMF=2"
echo "  - oba testy potwierdzily przelaczenie kanalu 6->11"
echo
echo "Wniosek: rekompilacja kernela NIE JEST POTRZEBNA"
pause

# ---- ASCII diagram ----
header "Diagram: Dwie sciezki CSA"

echo "  Komenda iw                  Beacon z CSA IE"
echo "      |                            |"
echo "      v                            v"
echo "  nl80211_channel_switch()    ieee80211_sta_process_chanswitch()"
echo "  (nl80211.c:11328)           (mlme.c:2752)"
echo "      |                            |"
echo "  switch(iftype) {             sprawdza CHANCTX_STA_CSA"
echo "    AP: ok                         |"
echo "    STA: -95 BLAD                  v"
echo "  }                         hwsim ma flage (linia 5587)"
echo "      |                            |"
echo "      v                            v"
echo "  ZABLOKOWANE                 SCIEZKA PROGRAMOWA"
echo "                              timer -> ch_switch_notify()"
echo "                                   |"
echo "                                   v"
echo "                              DZIALA"
echo
echo "Sciezka ADMIN: dla AP, P2P-GO, ADHOC, MESH - NIE dla STA"
echo "Sciezka BEACON: dla kazdego iftype - DZIALA na hwsim"
pause

header "Koniec demo"

echo "Kluczowe pliki zrodlowe kernela:"
echo "  net/wireless/nl80211.c                    - sciezka ADMIN"
echo "  net/mac80211/mlme.c                       - sciezka BEACON"
echo "  drivers/net/wireless/virtual/mac80211_hwsim.c - hwsim driver"
echo
echo "Testy potwierdzajace:"
echo "  raport/logs/direct_csa_2.6_20260610_101805.txt"
echo "  raport/logs/direct_csa_2.10_20260610_102002.txt"
echo
