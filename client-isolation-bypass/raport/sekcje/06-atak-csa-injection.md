# 06 — Atak: CSA Injection (Beacon-based + Action Frame)

**Data:** 5-9 czerwca 2026 (ciągłe)  
**Aktualizacja:** 9 czerwca 2026 — dodano Beacon CSA, BeaconStrike, potwierdzenia akademickie

## 1. Opis ataku

Channel Switch Announcement (CSA) to mechanizm 802.11h używany przez AP do informowania stacji o zmianie kanału. CSA może być dostarczone na dwa sposoby:

| Metoda | Subtype | Chroniona przez PMF? |
|--------|---------|---------------------|
| **Action Frame CSA** (subtype 13) | 13 — Action | hostapd < 2.7: NIE, ≥ 2.7: TAK |
| **Beacon CSA** (subtype 8, IE 37) | 8 — Beacon | **NIGDY** — Beacony są Non-Robust |

### 1.1 Kluczowa innowacja: Beacon CSA

Beacon frames (subtype 8) są **zawsze** klasyfikowane jako Non-Robust Management Frames przez 802.11w. Oznacza to, że nawet przy `ieee80211w=2` (PMF required), stacja MUSI przetwarzać Beacony, w tym zawarte w nich CSA Information Elements (tag 37).

**Inspiracja:** Politician (ESP32, `0ldev/Politician`) używa `_sendCsaBurst()` — wysyła burst Beaconów z CSA IE. BeaconStrike (`confnameless/BeaconStrike`) potwierdza tę technikę jako skuteczną przeciwko WPA3.

## 2. Implementacja

### 2.1 Moduł ataku: `beacon_csa.py`

Nowy moduł (484 linie) implementuje wielowektorowy atak CSA:

```python
class CsaInjectionEngine:
    def combined_attack(self):
        # 1. Beacon CSA burst — główny wektor (działa na wszystkich wersjach)
        self.send_beacon_csa_burst(count=30, switch_count=1)
        time.sleep(1.0)
        # 2. Action CSA burst — dodatkowy wektor (dla hostapd < 2.7)
        self.send_action_csa_burst(count=10)
        # 3. Deauth burst — fallback
        self.send_deauth_burst(count=5)
```

### 2.2 Struktura ramki Beacon CSA

```
RadioTap | Dot11(type=0, subtype=8, addr1=broadcast, addr2=ap_mac, addr3=ap_mac)
| Dot11Beacon(timestamp, beacon_interval, capabilities)
| Dot11Elt(ID=0, SSID)
| Dot11Elt(ID=1, Supported Rates)
| Dot11Elt(ID=3, DS Parameter Set = current_channel)
| Dot11Elt(ID=37, CSA: switch_mode=0x01, new_channel, switch_count)
```

CSA Information Element (tag 37) — 3 bajty:
- Byte 0: Channel Switch Mode (0x01 = ograniczenia TX)
- Byte 1: New Channel Number
- Byte 2: Channel Switch Count (0 = natychmiast)

### 2.3 Nowe podejście: `direct_hwsim_csa.py`

Ze względu na ograniczenia Mininet-WiFi (OVSAP nie tworzy prawdziwych asocjacji 802.11 w kernelu), stworzono alternatywny skrypt `raport/direct_hwsim_csa.py`, który:
1. Ładuje `mac80211_hwsim` i uruchamia `wmediumd` (separacja kanałów)
2. Uruchamia `hostapd` bezpośrednio na interfejsie hwsim (prawdziwy AP)
3. Uruchamia `wpa_supplicant` na drugim interfejsie (prawdziwa asocjacja 802.11)
4. Wstrzykuje Beacon CSA przez trzeci interfejs w trybie monitor
5. Weryfikuje czy stacja zmieniła kanał przez `iw dev wlanX info`

## 3. Wyniki testów (Mininet-WiFi OVSAP)

**Test 1: hostapd 2.10 — Action Frame CSA**
```
=== Pre-Test ===
  IP: 10.0.0.1  MAC: 96:85:b0:11:8c:e7

=== Sending Spoofed CSA Frames ===
  Frames sent: 3/30

=== Post-Test ===
  IP: 10.0.0.1  IP stable: True

[PASS] Station unaffected.
```

**Test 2: hostapd 2.6 — Action Frame CSA**
```
=== Pre-Test ===
  IP: 10.0.0.1  MAC: 7a:a4:c1:d2:ab:dd

=== Sending Spoofed CSA Frames ===
  Frames sent: 3/30

=== Post-Test ===
  IP: 10.0.0.1  IP stable: True

[PASS] Station unaffected.
```

**Test 3: Beacon CSA (Mininet-WiFi OVSAP)**
```
Frame builder: POTWIERDZONY (poprawna struktura Beacon CSA, tag 37)
Wysyłanie ramek: POTWIERDZONE (scapy potwierdza transmisję)
Reakcja stacji: BRAK — kernel nie ma asocjacji, nie wywołuje cfg80211_ch_switch_notify()
```

**Wynik:** NIEROZSTRZYGNIĘTY — ograniczenie środowiska wirtualnego. Testy na `direct_hwsim_csa.py` w toku.

## 4. Analiza — ograniczenia środowiska

### 4.1 Mininet-WiFi OVSAP
- AP ma interfejs w trybie AP, stacja w trybie managed
- Ale `iw dev wlan0 link` → "Not connected"
- Komunikacja IP przez bridging OVS/wmediumd, nie przez 802.11
- Kernel nie śledzi asocjacji → nie przetwarza CSA

### 4.2 mac80211_hwsim — analiza możliwości CSA (2026-06-09)
- Wszystkie interfejsy dzielą to samo wirtualne medium
- Zmiana kanału to parametr programowy, nie fizyczna izolacja częstotliwości
- **Rozwiązanie teoretyczne:** wmediumd modeluje separację kanałów

### 4.3 Rozwiązanie: direct_hwsim_csa.py — wyniki testów (2026-06-09)

Przeprowadzono testy z bezpośrednim hostapd + wpa_supplicant na hwsim:

| Test | Wynik |
|------|-------|
| Asocjacja 802.11 (PMF=0) | ✅ DZIAŁA — `CTRL-EVENT-CONNECTED` |
| Asocjacja 802.11 (PMF=2) | ✅ DZIAŁA — `CTRL-EVENT-CONNECTED` |
| Iniekcja Beacon CSA (monitor mode) | ✅ DZIAŁA — ramki wysyłane przez scapy |
| **Przełączenie kanału STA (`iw switch channel`)** | ❌ `Operation not supported (-95)` |

### 4.4 POPRAWIONA DIAGNOZA (2026-06-10) — Analiza kodu źródłowego kernela 6.19.14

**Wstępna diagnoza (2026-06-09) była błędna.** `CONFIG_CFG80211_CERTIFICATION_ONUS` **NIE** jest wymagane do przełączania kanałów na stacjach przez Beacon CSA. Przeprowadzona analiza kodu źródłowego kernela 6.19.14 wykazała dwie niezależne ścieżki CSA:

#### Ścieżka A: ADMIN — `NL80211_CMD_CHANNEL_SWITCH` (komenda `iw`)

Funkcja `nl80211_channel_switch()` w `net/wireless/nl80211.c` (linia 11328):

```c
switch (dev->ieee80211_ptr->iftype) {
case NL80211_IFTYPE_AP:
case NL80211_IFTYPE_P2P_GO:
    // ... dozwolone
    break;
case NL80211_IFTYPE_ADHOC:
    // ... dozwolone
    break;
case NL80211_IFTYPE_MESH_POINT:
    // ... dozwolone
    break;
default:                              // ← STA trafia tutaj!
    return -EOPNOTSUPP;               // ← źródło błędu -95
}
```

**Blokada jest hardcodowana w switch(iftype)** — nie ma związku z `CERTIFICATION_ONUS`. Opcja `CERTIFICATION_ONUS` kontroluje tylko sub-opcje relaksacji regulacyjnej (`REG_RELAX_NO_IR`, `REG_CELLULAR_HINTS`).

#### Ścieżka B: BEACON CSA RECEIVE — `ieee80211_sta_process_chanswitch()`

Funkcja w `net/mac80211/mlme.c` (linia 2752) — przetwarza odebrany Beacon z CSA IE:

- **Brak bramki iftype** — funkcja jest specyficzna dla STA (używa `sdata->u.mgd`)
- Sprawdza tylko flagę sprzętową: `CHANCTX_STA_CSA`
- **hwsim ma tę flagę ustawioną**: `mac80211_hwsim.c:5587` — `ieee80211_hw_set(hw, CHANCTX_STA_CSA)`
- hwsim **nie ma** callbacku `ops->channel_switch` — mac80211 używa **ścieżki programowej** (timer + `cfg80211_ch_switch_notify()`)

**Wniosek:** Ścieżka Beacon CSA działa na stockowym kernelu Kali — NIE jest wymagana rekompilacja.

### 4.5 WYNIKI TESTÓW (2026-06-10) — Beacon CSA Injection

Testy przeprowadzone na kernelu 6.19.14+kali-amd64, `# CONFIG_CFG80211_CERTIFICATION_ONUS is not set`:

| Test | Hostapd | PMF | Wynik | Dowód |
|------|---------|-----|-------|-------|
| Beacon CSA injection | 2.6 | 2 | 🎯 **SUCCESS** — ch6→ch11 | `logs/direct_csa_2.6_20260610_101805.txt` |
| Beacon CSA injection | 2.10 | 2 | 🎯 **SUCCESS** — ch6→ch11 | `logs/direct_csa_2.10_20260610_102002.txt` |
| **Pełny exploit (CSA + Evil Twin)** | 2.6 | 2 | 🎯 **SUCCESS** — reassocjacja | `logs/direct_csa_2.6_20260610_103338.txt` |
| Monitor interface workaround | — | — | ❌ DEAD END | — |

**Pełny łańcuch ataku potwierdzony:**
1. Legit AP na kanale 6, PMF=2
2. Stacja łączy się (Auth → Assoc → 4-Way Handshake → CONNECTED)
3. Iniekcja 50 Beacon CSA frames (subtype 8, IE 37): "AP przenosi się na kanał 11"
4. Stacja przełącza kanał: 6 → 11
5. Evil Twin AP uruchomiony na kanale 11 (ten sam SSID, PMF=0)
6. Stacja reassocjuje się do Evil Twin
7. Handshake przechwycony (PCAP zapisany)

**UWAGA:** Separacja kanałów (wmediumd) nie była aktywna w tych testach — stacja słyszy oba AP. W środowisku fizycznym przełączenie kanału automatycznie izoluje stację od legalnego AP.

### 4.6 WIDS EVASION — Analiza detekcji (2026-06-10)

Przeprowadzono testy z uruchomionym WIDS (`scapy_sniffer.py`) na interfejsie injection podczas ataku Beacon CSA.

**scapy_sniffer.py:**
- Monitoruje ramki zarządzania: Beacon (8), Deauth (12), Disassoc (10), Action (13)
- Ramki Deauth i Disassoc są oznaczone jako `[!]` (PMF-relevant)
- Beacon CSA używa **subtype 8 (Beacon)** — NIE jest oznaczany jako alert
- Sniffer widzi wstrzyknięte Beacony jako normalny ruch — **nie generuje alertów**

**Kismet (teoretycznie):**
- `DEAUTHFLOOD` — nie dotyczy (brak ramek Deauth)
- `CHANCHANGE` — niska szansa detekcji (wymaga śledzenia zmian kanału klienta)
- `APSPOOF` — **może zadziałać na fizycznym sprzęcie** (Evil Twin ma inny MAC, ten sam SSID)

**Wynik:** Beacon CSA injection **omija standardową detekcję WIDS**. Ramki Beacon (subtype 8) są normalnym ruchem sieciowym — żaden standardowy WIDS nie flaguje Beaconów jako anomalii. Jedyną metodą detekcji jest inspekcja CSA Information Element (tag 37) wewnątrz Beaconów, co wymaga głębokiej analizy ramek (deep packet inspection).

**WIDS PCAP:** `raport/pcaps/csa_injection/wids_*.pcap`

## 5. Potwierdzenia zewnętrzne

| Źródło | Typ | Opis |
|--------|-----|------|
| **Politician** (0ldev, ESP32) | Implementacja | `_sendCsaBurst()` używa Beacon CSA do ataku |
| **BeaconStrike** (confnameless) | Narzędzie | "The Ultimate WPA3 Channel-Switch Exploit Toolkit" — Beacon CSA injection |
| **"802.11 MiTM Attack Using Channel Switch Announcement"** | Publikacja naukowa | Springer 2020 — Evil Twin MiTM przez CSA na rzeczywistym sprzęcie |
| **"On the detection of CSA Attack in 802.11 networks"** | Publikacja naukowa | IEEE 2021 — detekcja RSSI-based, potwierdza realność ataku |
| **CSA Attack Tracker** | Publikacja naukowa | IEEE Access 2024 — WIDS dla Multi-Channel MiTM przez CSA |
| **hostapd commit 4c8d4e8e** (2016-04) | Kod źródłowy | Zmiana klasyfikacji CSA: Non-Robust → Robust |

## 6. Wnioski

1. **Beacon CSA NIE jest chroniony przez PMF** — to luka fundamentalna w 802.11w
2. Mininet-WiFi OVSAP nie nadaje się do testowania CSA — potrzebna prawdziwa asocjacja kernelowa
3. `direct_hwsim_csa.py` rozwiązuje problem przez bezpośrednie hostapd + wpa_supplicant
4. Atak potwierdzony przez Politician (ESP32), BeaconStrike, i 3 publikacje naukowe

---

**[✗ SCREENSHOT: Wireshark — ramka Beacon CSA z widocznym elementem CSA (tag 37)]**  
**[✗ SCREENSHOT: Wireshark — ramka Action Frame CSA (subtype 13)]**  
**[✗ SCREENSHOT: Terminal — output beacon_csa.py pokazujący strukturę ramek]**  
**[✗ SCREENSHOT: Diagram — architektura direct_hwsim_csa.py: hwsim → hostapd → wpa_supplicant → scapy injection]**
