# 06 — Atak: CSA Injection (Beacon-based + Action Frame)

**Data:** 5-9 czerwca 2026 (ciagle)  
**Aktualizacja:** 9 czerwca 2026 — dodano Beacon CSA, BeaconStrike, potwierdzenia akademickie

## 1. Opis ataku

Channel Switch Announcement (CSA) to mechanizm 802.11h uzywany przez AP do informowania stacji o zmianie kanalu. CSA moze byc dostarczone na dwa sposoby:

| Metoda | Subtype | Chroniona przez PMF? |
|--------|---------|---------------------|
| **Action Frame CSA** (subtype 13) | 13 — Action | hostapd < 2.7: NIE, ≥ 2.7: TAK |
| **Beacon CSA** (subtype 8, IE 37) | 8 — Beacon | **NIGDY** — Beacony sa Non-Robust |

### 1.1 Kluczowa innowacja: Beacon CSA

Beacon frames (subtype 8) sa **zawsze** klasyfikowane jako Non-Robust Management Frames przez 802.11w. Oznacza to, ze nawet przy `ieee80211w=2` (PMF required), stacja MUSI przetwarzac Beacony, w tym zawarte w nich CSA Information Elements (tag 37).

**Inspiracja:** Politician (ESP32, `0ldev/Politician`) uzywa `_sendCsaBurst()` — wysyla burst Beaconow z CSA IE. BeaconStrike (`confnameless/BeaconStrike`) potwierdza te technike jako skuteczna przeciwko WPA3.

## 2. Implementacja

### 2.1 Modul ataku: `beacon_csa.py`

Nowy modul (484 linie) implementuje wielowektorowy atak CSA:

```python
class CsaInjectionEngine:
    def combined_attack(self):
        # 1. Beacon CSA burst — glowny wektor (dziala na wszystkich wersjach)
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

### 2.3 Nowe podejscie: `direct_hwsim_csa.py`

Ze wzgledu na ograniczenia Mininet-WiFi (OVSAP nie tworzy prawdziwych asocjacji 802.11 w kernelu), stworzono alternatywny skrypt `raport/direct_hwsim_csa.py`, ktory:
1. Laduje `mac80211_hwsim` bez Mininet-WiFi.
2. Uruchamia legalny `hostapd` bezposrednio na interfejsie hwsim (prawdziwy AP).
3. Umieszcza dwoch klientow w osobnych `ip netns`, zeby ping klient-klient byl rzeczywistym ruchem przez AP.
4. Weryfikuje baseline: legalny AP ma `ap_isolate=1`, wiec `sta1 -> sta2` nie dziala.
5. Uruchamia Evil Twin z tym samym SSID, ale bez izolacji (`ap_isolate=0`).
6. Wstrzykuje Beacon CSA przez osobny interfejs monitor.
7. Czeka na reassocjacje obu klientow do Evil Twin.
8. Weryfikuje przejecie polityki ruchu: `sta1 -> sta2` dziala na Evil Twin.
9. Zapisuje PCAP-y dla pingow przed/po i log runu.

## 3. Wyniki testow (Mininet-WiFi OVSAP)

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
Wysylanie ramek: POTWIERDZONE (scapy potwierdza transmisje)
Reakcja stacji: BRAK — kernel nie ma asocjacji, nie wywoluje cfg80211_ch_switch_notify()
```

**Wynik:** NIEROZSTRZYGNIETY — ograniczenie srodowiska wirtualnego. Testy na `direct_hwsim_csa.py` w toku.

## 4. Analiza — ograniczenia srodowiska

### 4.1 Mininet-WiFi OVSAP
- AP ma interfejs w trybie AP, stacja w trybie managed
- Ale `iw dev wlan0 link` → "Not connected"
- Komunikacja IP przez bridging OVS/wmediumd, nie przez 802.11
- Kernel nie sledzi asocjacji → nie przetwarza CSA

### 4.2 mac80211_hwsim — analiza mozliwosci CSA (2026-06-09)
- Wszystkie interfejsy dziela to samo wirtualne medium
- Zmiana kanalu to parametr programowy, nie fizyczna izolacja czestotliwosci
- **Rozwiazanie teoretyczne:** wmediumd modeluje separacje kanalow

### 4.3 Rozwiazanie: direct_hwsim_csa.py — wyniki testow (2026-06-09)

Przeprowadzono testy z bezposrednim hostapd + wpa_supplicant na hwsim:

| Test | Wynik |
|------|-------|
| Asocjacja 802.11 (PMF=0) | DZIALA — `CTRL-EVENT-CONNECTED` |
| Asocjacja 802.11 (PMF=2) | DZIALA — `CTRL-EVENT-CONNECTED` |
| Iniekcja Beacon CSA (monitor mode) | DZIALA — ramki wysylane przez scapy |
| **Przelaczenie kanalu STA (`iw switch channel`)** | `Operation not supported (-95)` |

### 4.4 POPRAWIONA DIAGNOZA (2026-06-10) — Analiza kodu zrodlowego kernela 6.19.14

**Wstepna diagnoza (2026-06-09) byla bledna.** `CONFIG_CFG80211_CERTIFICATION_ONUS` **NIE** jest wymagane do przelaczania kanalow na stacjach przez Beacon CSA. Przeprowadzona analiza kodu zrodlowego kernela 6.19.14 wykazala dwie niezalezne sciezki CSA:

#### Sciezka A: ADMIN — `NL80211_CMD_CHANNEL_SWITCH` (komenda `iw`)

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
    return -EOPNOTSUPP;               // ← zrodlo bledu -95
}
```

**Blokada jest hardcodowana w switch(iftype)** — nie ma zwiazku z `CERTIFICATION_ONUS`. Opcja `CERTIFICATION_ONUS` kontroluje tylko sub-opcje relaksacji regulacyjnej (`REG_RELAX_NO_IR`, `REG_CELLULAR_HINTS`).

#### Sciezka B: BEACON CSA RECEIVE — `ieee80211_sta_process_chanswitch()`

Funkcja w `net/mac80211/mlme.c` (linia 2752) — przetwarza odebrany Beacon z CSA IE:

- **Brak bramki iftype** — funkcja jest specyficzna dla STA (uzywa `sdata->u.mgd`)
- Sprawdza tylko flage sprzetowa: `CHANCTX_STA_CSA`
- **hwsim ma te flage ustawiona**: `mac80211_hwsim.c:5587` — `ieee80211_hw_set(hw, CHANCTX_STA_CSA)`
- hwsim **nie ma** callbacku `ops->channel_switch` — mac80211 uzywa **sciezki programowej** (timer + `cfg80211_ch_switch_notify()`)

**Wniosek:** Sciezka Beacon CSA dziala na stockowym kernelu Kali — NIE jest wymagana rekompilacja.

### 4.5 WYNIKI TESTOW (2026-06-10) — Beacon CSA Injection

Testy przeprowadzone na kernelu 6.19.14+kali-amd64, `# CONFIG_CFG80211_CERTIFICATION_ONUS is not set`:

| Test | Hostapd | PMF | Wynik | Dowod |
|------|---------|-----|-------|-------|
| Beacon CSA injection | 2.6 | 2 | **SUCCESS** — ch6→ch11 | `logs/direct_csa_2.6_20260610_101805.txt` |
| Beacon CSA injection | 2.10 | 2 | **SUCCESS** — ch6→ch11 | `logs/direct_csa_2.10_20260610_102002.txt` |
| **Pelny exploit (CSA + Evil Twin)** | 2.6 | 2 | **SUCCESS** — reassocjacja | `logs/direct_csa_2.6_20260610_103338.txt` |
| Monitor interface workaround | — | — | DEAD END | — |

**Pelny lancuch ataku potwierdzony:**
1. Legit AP na kanale 6, PMF=2
2. Stacja laczy sie (Auth → Assoc → 4-Way Handshake → CONNECTED)
3. Iniekcja 50 Beacon CSA frames (subtype 8, IE 37): "AP przenosi sie na kanal 11"
4. Stacja przelacza kanal: 6 → 11
5. Evil Twin AP uruchomiony na kanale 11 (ten sam SSID, PMF=0)
6. Stacja reassocjuje sie do Evil Twin
7. Handshake przechwycony (PCAP zapisany)

**UWAGA:** Separacja kanalow (wmediumd) nie byla aktywna w tych testach — stacja slyszy oba AP. W srodowisku fizycznym przelaczenie kanalu automatycznie izoluje stacje od legalnego AP.

### 4.5.1 WYNIKI TESTU DWOCH KLIENTOW — Client Isolation bypass (2026-06-11)

Zaktualizowany przebieg demonstracyjny rozszerza CSA + Evil Twin o dowod obejscia izolacji klientow:

| Faza | Wynik | Dowod |
|------|-------|-------|
| Legalny AP, 2 STA, `ap_isolate=1` | `BASELINE_ASSOC_PASS` | Oba klienty polaczone z BSSID legalnego AP |
| Ping `sta1 -> sta2` na legalnym AP | `BASELINE_ISOLATION_PASS` | `5 packets transmitted, 0 received, 100% packet loss` |
| Beacon CSA na oba STA | `CSA_SWITCH_PASS` | Oba klienty przeszly z kanalu 6 na 11 |
| Reassociation do Evil Twin | `EVIL_TWIN_REASSOC_PASS` | Oba klienty polaczone z BSSID Evil Twin |
| Ping `sta1 -> sta2` na Evil Twin | `EVIL_TWIN_PING_PASS` | `5 packets transmitted, 5 received, 0% packet loss` |

Komenda runu:

```bash
sudo python3 /mnt/hgfs/demo/demo_atak_csa.py --yes
```

Artefakty:

```text
raport/pcaps/csa_injection/baseline_isolation_20260611_113304.pcap
raport/pcaps/csa_injection/evil_twin_ping_20260611_113304.pcap
raport/logs/direct_csa_2.10_20260611_113347.txt
```

Wniosek dla demonstracji: oryginalna polityka `Client Isolation` przestaje obowiazywac po reassocjacji do Evil Twin, poniewaz klienci sa juz przypieci do AP kontrolowanego przez operatora, gdzie izolacja jest wylaczona.

### 4.6 WIDS EVASION — Analiza detekcji (2026-06-10)

Przeprowadzono testy z uruchomionym WIDS (`scapy_sniffer.py`) na interfejsie injection podczas ataku Beacon CSA.

**scapy_sniffer.py:**
- Monitoruje ramki zarzadzania: Beacon (8), Deauth (12), Disassoc (10), Action (13)
- Ramki Deauth i Disassoc sa oznaczone jako `[!]` (PMF-relevant)
- Beacon CSA uzywa **subtype 8 (Beacon)** — NIE jest oznaczany jako alert
- Sniffer widzi wstrzykniete Beacony jako normalny ruch — **nie generuje alertow**

**Kismet (teoretycznie):**
- `DEAUTHFLOOD` — nie dotyczy (brak ramek Deauth)
- `CHANCHANGE` — niska szansa detekcji (wymaga sledzenia zmian kanalu klienta)
- `APSPOOF` — **moze zadzialac na fizycznym sprzecie** (Evil Twin ma inny MAC, ten sam SSID)

**Wynik:** Beacon CSA injection **omija standardowa detekcje WIDS**. Ramki Beacon (subtype 8) sa normalnym ruchem sieciowym — zaden standardowy WIDS nie flaguje Beaconow jako anomalii. Jedyna metoda detekcji jest inspekcja CSA Information Element (tag 37) wewnatrz Beaconow, co wymaga glebokiej analizy ramek (deep packet inspection).

**WIDS PCAP:** `raport/pcaps/csa_injection/wids_*.pcap`

## 5. Potwierdzenia zewnetrzne

| Zrodlo | Typ | Opis |
|--------|-----|------|
| **Politician** (0ldev, ESP32) | Implementacja | `_sendCsaBurst()` uzywa Beacon CSA do ataku |
| **BeaconStrike** (confnameless) | Narzedzie | "The Ultimate WPA3 Channel-Switch Exploit Toolkit" — Beacon CSA injection |
| **"802.11 MiTM Attack Using Channel Switch Announcement"** | Publikacja naukowa | Springer 2020 — Evil Twin MiTM przez CSA na rzeczywistym sprzecie |
| **"On the detection of CSA Attack in 802.11 networks"** | Publikacja naukowa | IEEE 2021 — detekcja RSSI-based, potwierdza realnosc ataku |
| **CSA Attack Tracker** | Publikacja naukowa | IEEE Access 2024 — WIDS dla Multi-Channel MiTM przez CSA |
| **hostapd commit 4c8d4e8e** (2016-04) | Kod zrodlowy | Zmiana klasyfikacji CSA: Non-Robust → Robust |

## 6. Wnioski

1. **Beacon CSA NIE jest chroniony przez PMF** — to luka fundamentalna w 802.11w
2. Mininet-WiFi OVSAP nie nadaje sie do testowania CSA — potrzebna prawdziwa asocjacja kernelowa
3. `direct_hwsim_csa.py` rozwiazuje problem przez bezposrednie hostapd + wpa_supplicant, bez Mininet-WiFi
4. Dwuklientowy run potwierdza zmiane polityki L2: ping zablokowany na legalnym AP dziala po przejsciu na Evil Twin
5. Atak potwierdzony przez Politician (ESP32), BeaconStrike, i 3 publikacje naukowe

---

**[screenshot: Wireshark — ramka Beacon CSA z widocznym elementem CSA (tag 37)]**  
**[screenshot: Wireshark — ramka Action Frame CSA (subtype 13)]**  
**[screenshot: Terminal — output beacon_csa.py pokazujacy strukture ramek]**  
**[screenshot: Diagram — architektura direct_hwsim_csa.py: legit AP z izolacja → 2 STA → CSA → Evil Twin bez izolacji]**
**[screenshot: Terminal — `BASELINE_ISOLATION_PASS` oraz `EVIL_TWIN_PING_PASS`]**
