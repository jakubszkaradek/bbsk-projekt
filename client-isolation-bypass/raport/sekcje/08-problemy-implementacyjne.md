# 08 — Problemy Implementacyjne i Rozwiazania

**Data:** 9-10 czerwca 2026

## 1. Przeglad napotkanych problemow

Podczas implementacji ataku PMF Bypass napotkano szereg problemow technicznych na roznych warstwach stosu: od konfiguracji SSH, przez Mininet-WiFi, po kernel Linux.

## 2. Problemy — warstwa srodowiskowa

### 2.1 PowerShell interpretuje przekierowania przed SSH

**Objaw:** `2>&1` i `2>/dev/null` w komendach `ssh kali-lab "..."` sa konsumowane lokalnie przez PowerShell, nie przekazywane do VM.

**Rozwiazanie:** Zawsze pisz skrypty do `raport/` (widoczne przez VMware share `/mnt/hgfs/`) i wykonuj przez sciezke absolutna: `ssh kali-lab "sudo python3 /mnt/hgfs/raport/script.py"`.

### 2.2 Nazwy interfejsow w namespace Mininet

**Objaw:** `iw dev sta1-wlan0 link` → "No such device".

**Przyczyna:** Wewnatrz namespace Mininet, interfejs nazywa sie `wlan0` (bez prefiksu nazwy stacji).

**Rozwiazanie:** Uzywaj stalej `IFACE = "wlan0"` we wszystkich skryptach dzialajacych wewnatrz namespace.

### 2.3 `node.wintfs[0].mac` zwraca `None`

**Objaw:** Ramki scapy z nieprawidlowym adresem MAC.

**Rozwiazanie:** Ekstrakcja MAC z `ip -c=never link show wlan0` przez regex `link/ether ([0-9a-f:]+)`.

### 2.4 ANSI escape codes w `ip link`

**Objaw:** Regex nie matchuje adresu MAC.

**Rozwiazanie:** Flaga `-c=never` we wszystkich komendach `ip`.

## 3. Problemy — warstwa Mininet-WiFi

### 3.1 mininet-wifi master niekompatybilny z kernelem 6.x

**Objaw:** `get_hwsim_list()` nie znajduje interfejsow — debugfs nie zawiera PID.

**Rozwiazanie:** Latka w `/opt/mininet-wifi/mn_wifi/module.py` — zamiana `grep %05d % getpid()` na `find ... | sed`.

### 3.2 OVSAP nie tworzy prawdziwych asocjacji 802.11

**Problem:** Mininet-WiFi w trybie `failMode="standalone"` uzywa bridgingu OVS zamiast prawdziwych polaczen 802.11. Stacje dostaja IP przez DHCP, ale `iw dev wlan0 link` pokazuje "Not connected".

**Wplyw:** Kernel nie sledzi asocjacji → `ieee80211_sta_process_chanswitch()` nie jest wywolywane → Beacon CSA nie dziala.

**Rozwiazanie:** Uzycie bezposredniego `hostapd + wpa_supplicant` na hwsim (bez Mininet-WiFi) — skrypt `direct_hwsim_csa.py`.

### 3.3 wmediumd — problemy z konfiguracja

**Problem:** wmediumd 0.5 wymaga poprawnej konfiguracji z lista MAC adresow interfejsow. Skladnia `ifaces_media_matrix` moze nie byc wspierana we wszystkich wersjach.

**Rozwiazanie:** Minimalna konfiguracja z `default_prob = 1.0` (wszystkie interfejsy slysza sie nawzajem). Separacja kanalow w hwsim jest obslugiwana na poziomie phy.

## 4. Problemy — warstwa kernela

### 4.1 Dwie sciezki CSA — kluczowe odkrycie

Najwazniejszy problem techniczny: poczatkowo blednie zdiagnozowano `CONFIG_CFG80211_CERTIFICATION_ONUS` jako bloker.

**Bledna diagnoza (2026-06-09):** Kernel wymaga rekompilacji z `CERTIFICATION_ONUS=y`.

**Poprawna diagnoza (2026-06-10):** Analiza kodu zrodlowego kernela 6.19.14 wykazala:

```
Sciezka ADMIN (iw dev wlan0 switch channel):
  nl80211_channel_switch() → switch(iftype) → default: -EOPNOTSUPP
  └─ STA trafia w default → ZABLOKOWANE, bez zwiazku z CERTIFICATION_ONUS

Sciezka BEACON CSA (odebranie Beacona z IE 37):
  ieee80211_sta_process_chanswitch() → CHANCTX_STA_CSA [ok] → software path
  └─ BRAK bramki iftype, hwsim ma flage → DZIALA
```

**Rozwiazanie:** Rekompilacja kernela NIE jest potrzebna. Beacon CSA injection dziala na stockowym kernelu Kali.

### 4.2 Tcpdump na interfejsie AP nie przechwytuje ramek EAPOL

**Problem:** `tcpdump -i <iface>` na interfejsie w trybie AP nie widzi ramek zarzadzania WiFi (link-type EN10MB zamiast IEEE802_11_RADIO).

**Rozwiazanie:** Uzycie monitor mode do przechwytywania: `iw dev <iface> set type monitor` przed tcpdump.

## 5. Podsumowanie — nauczone lekcje

| Lekcja | Konsekwencja |
|--------|-------------|
| Nie ufaj `2>&1` w SSH przez PowerShell | Pisz skrypty, wykonuj przez sciezke absolutna |
| Nazwy interfejsow w namespace ≠ nazwy Mininet | Uzywaj stalej `wlan0` |
| `node.wintfs[0].mac` = None w Mininet-WiFi master | Ekstrahuj z `ip link` |
| Mininet-WiFi OVSAP ≠ prawdziwy 802.11 | Uzywaj bezposredniego hostapd + wpa_supplicant |
| `CERTIFICATION_ONUS` ≠ CSA na STA | Beacon CSA dziala bez zmian w kernelu |
| Dwie sciezki CSA (admin vs receive) | `iw switch channel` NIE testuje Beacon CSA |
