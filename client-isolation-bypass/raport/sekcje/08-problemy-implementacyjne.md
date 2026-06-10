# 08 — Problemy Implementacyjne i Rozwiązania

**Data:** 9-10 czerwca 2026

## 1. Przegląd napotkanych problemów

Podczas implementacji ataku PMF Bypass napotkano szereg problemów technicznych na różnych warstwach stosu: od konfiguracji SSH, przez Mininet-WiFi, po kernel Linux.

## 2. Problemy — warstwa środowiskowa

### 2.1 PowerShell interpretuje przekierowania przed SSH

**Objaw:** `2>&1` i `2>/dev/null` w komendach `ssh kali-lab "..."` są konsumowane lokalnie przez PowerShell, nie przekazywane do VM.

**Rozwiązanie:** Zawsze pisz skrypty do `raport/` (widoczne przez VMware share `/mnt/hgfs/`) i wykonuj przez ścieżkę absolutną: `ssh kali-lab "sudo python3 /mnt/hgfs/raport/script.py"`.

### 2.2 Nazwy interfejsów w namespace Mininet

**Objaw:** `iw dev sta1-wlan0 link` → "No such device".

**Przyczyna:** Wewnątrz namespace Mininet, interfejs nazywa się `wlan0` (bez prefiksu nazwy stacji).

**Rozwiązanie:** Używaj stałej `IFACE = "wlan0"` we wszystkich skryptach działających wewnątrz namespace.

### 2.3 `node.wintfs[0].mac` zwraca `None`

**Objaw:** Ramki scapy z nieprawidłowym adresem MAC.

**Rozwiązanie:** Ekstrakcja MAC z `ip -c=never link show wlan0` przez regex `link/ether ([0-9a-f:]+)`.

### 2.4 ANSI escape codes w `ip link`

**Objaw:** Regex nie matchuje adresu MAC.

**Rozwiązanie:** Flaga `-c=never` we wszystkich komendach `ip`.

## 3. Problemy — warstwa Mininet-WiFi

### 3.1 mininet-wifi master niekompatybilny z kernelem 6.x

**Objaw:** `get_hwsim_list()` nie znajduje interfejsów — debugfs nie zawiera PID.

**Rozwiązanie:** Łatka w `/opt/mininet-wifi/mn_wifi/module.py` — zamiana `grep %05d % getpid()` na `find ... | sed`.

### 3.2 OVSAP nie tworzy prawdziwych asocjacji 802.11

**Problem:** Mininet-WiFi w trybie `failMode="standalone"` używa bridgingu OVS zamiast prawdziwych połączeń 802.11. Stacje dostają IP przez DHCP, ale `iw dev wlan0 link` pokazuje "Not connected".

**Wpływ:** Kernel nie śledzi asocjacji → `ieee80211_sta_process_chanswitch()` nie jest wywoływane → Beacon CSA nie działa.

**Rozwiązanie:** Użycie bezpośredniego `hostapd + wpa_supplicant` na hwsim (bez Mininet-WiFi) — skrypt `direct_hwsim_csa.py`.

### 3.3 wmediumd — problemy z konfiguracją

**Problem:** wmediumd 0.5 wymaga poprawnej konfiguracji z listą MAC adresów interfejsów. Składnia `ifaces_media_matrix` może nie być wspierana we wszystkich wersjach.

**Rozwiązanie:** Minimalna konfiguracja z `default_prob = 1.0` (wszystkie interfejsy słyszą się nawzajem). Separacja kanałów w hwsim jest obsługiwana na poziomie phy.

## 4. Problemy — warstwa kernela

### 4.1 Dwie ścieżki CSA — kluczowe odkrycie

Najważniejszy problem techniczny: początkowo błędnie zdiagnozowano `CONFIG_CFG80211_CERTIFICATION_ONUS` jako bloker.

**Błędna diagnoza (2026-06-09):** Kernel wymaga rekompilacji z `CERTIFICATION_ONUS=y`.

**Poprawna diagnoza (2026-06-10):** Analiza kodu źródłowego kernela 6.19.14 wykazała:

```
Ścieżka ADMIN (iw dev wlan0 switch channel):
  nl80211_channel_switch() → switch(iftype) → default: -EOPNOTSUPP
  └─ STA trafia w default → ZABLOKOWANE, bez związku z CERTIFICATION_ONUS

Ścieżka BEACON CSA (odebranie Beacona z IE 37):
  ieee80211_sta_process_chanswitch() → CHANCTX_STA_CSA ✓ → software path
  └─ BRAK bramki iftype, hwsim ma flagę → DZIAŁA
```

**Rozwiązanie:** Rekompilacja kernela NIE jest potrzebna. Beacon CSA injection działa na stockowym kernelu Kali.

### 4.2 Tcpdump na interfejsie AP nie przechwytuje ramek EAPOL

**Problem:** `tcpdump -i <iface>` na interfejsie w trybie AP nie widzi ramek zarządzania WiFi (link-type EN10MB zamiast IEEE802_11_RADIO).

**Rozwiązanie:** Użycie monitor mode do przechwytywania: `iw dev <iface> set type monitor` przed tcpdump.

## 5. Podsumowanie — nauczone lekcje

| Lekcja | Konsekwencja |
|--------|-------------|
| Nie ufaj `2>&1` w SSH przez PowerShell | Pisz skrypty, wykonuj przez ścieżkę absolutną |
| Nazwy interfejsów w namespace ≠ nazwy Mininet | Używaj stałej `wlan0` |
| `node.wintfs[0].mac` = None w Mininet-WiFi master | Ekstrahuj z `ip link` |
| Mininet-WiFi OVSAP ≠ prawdziwy 802.11 | Używaj bezpośredniego hostapd + wpa_supplicant |
| `CERTIFICATION_ONUS` ≠ CSA na STA | Beacon CSA działa bez zmian w kernelu |
| Dwie ścieżki CSA (admin vs receive) | `iw switch channel` NIE testuje Beacon CSA |
