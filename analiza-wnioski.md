# Analiza i Wnioski — Projekt BBSK

## 1. Główny wniosek: PMF (802.11w) nie chroni przed Beacon CSA

Protected Management Frames chronią przed sfałszowanymi ramkami Deauth i Disassoc.
Ale **nie chronią przed Beacon CSA Injection** ponieważ Beacon (802.11 subtype 8)
jest zawsze klasyfikowany jako Non-Robust Management Frame.

Atak działa na wszystkich testowanych wersjach hostapd (2.6, 2.10)
niezależnie od ustawienia `ieee80211w=2` (PMF required).

## 2. Analiza techniczna

Kernel Linux ma dwie niezależne ścieżki CSA:

**Ścieżka ADMIN** (`iw dev wlan0 switch channel`)
- `nl80211_channel_switch()` w `net/wireless/nl80211.c`
- Hardcodowany `switch(iftype)` — STA trafia w `default: -EOPNOTSUPP`
- **Zablokowane**, bez związku z CERTIFICATION_ONUS

**Ścieżka BEACON CSA** (odebranie Beacona z IE 37)
- `ieee80211_sta_process_chanswitch()` w `net/mac80211/mlme.c`
- Brak bramki iftype — sprawdza tylko `CHANCTX_STA_CSA`
- hwsim ma flagę ustawioną (linia 5587)
- **Działa** na stockowym kernelu Kali bez rekompilacji

## 3. Wnioski praktyczne

- `CONFIG_CFG80211_CERTIFICATION_ONUS` **nie jest potrzebne** do ataku
- Aktualizacja hostapd do >= 2.7 **nie chroni** przed Beacon CSA
- Beacon CSA **omija standardowe WIDS** (scapy_sniffer, Kismet)
- Jedyna metoda detekcji: deep packet inspection CSA IE (tag 37)
- Pełna separacja kanałów wymaga fizycznego sprzętu WiFi

## 4. Rekomendacje

Dla administratorów:
- PMF to za mało — potrzebne dodatkowe monitorowanie anomalii RSSI
- WIDS powinien inspekcjonować CSA Information Elements
- Rozważyć ograniczenie mocy nadawania AP

Dla badaczy:
- hwsim jest wystarczający do testowania Beacon CSA (nie wymaga rekompilacji)
- wmediumd blokuje ramki injection — używać bez wmediumd
- Force-disconnect symuluje fizyczną izolację kanałów

## 5. Pliki kluczowe

| Plik | Opis |
|------|------|
| `kuba-pmf-bypass/raport/direct_hwsim_csa.py` | Główny exploit |
| `kuba-pmf-bypass/raport/sekcje/06-atak-csa-injection.md` | Analiza techniczna |
| `kuba-pmf-bypass/raport/sekcje/09-wnioski.md` | Wnioski szczegółowe |
| `kuba-pmf-bypass/demo/` | Skrypty demonstracyjne |
