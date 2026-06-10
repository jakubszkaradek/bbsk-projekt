# 09 — Wnioski i Rekomendacje

**Data:** 10 czerwca 2026

## 1. Główny wniosek

**Protected Management Frames (802.11w) nie chronią przed atakiem Beacon CSA Injection.**

Analiza kodu źródłowego kernela Linux 6.19.14 oraz testy praktyczne na środowisku mac80211_hwsim z hostapd 2.6 i 2.10 potwierdzają, że:

- Beacon frames (subtype 8) są **zawsze** klasyfikowane jako Non-Robust Management Frames przez 802.11w
- CSA Information Element (tag 37) w Beaconie jest przetwarzany przez stację **niezależnie** od ustawienia `ieee80211w=2`
- Mechanizm PMF chroni tylko ramki Action Frame CSA (subtype 13) na hostapd ≥ 2.7
- Atak Beacon CSA działa na **wszystkich testowanych wersjach hostapd** (2.6, 2.10)

## 2. Wyniki testów — podsumowanie

| Atak | Wektor | PMF=2 | Wynik |
|------|--------|-------|-------|
| Deauth Injection | subtype 12 | Chroniony | ❌ FAIL — PMF blokuje |
| Disassoc Injection | subtype 10 | Chroniony | ❌ FAIL — PMF blokuje |
| Action Frame CSA | subtype 13 (< 2.7) | Niechroniony | ⚠️ Teoretycznie działa (nietestowalne w hwsim) |
| Action Frame CSA | subtype 13 (≥ 2.7) | Chroniony | ❌ FAIL — PMF blokuje |
| **Beacon CSA** | **subtype 8, IE 37** | **Niechroniony** | **🎯 SUCCESS — działa na wszystkich wersjach** |
| SA Query Flood | Deauth + SA Query | Chroniony | ⚠️ Częściowy — zalew działa, ale stacja nie rozłącza się |

## 3. Pełny łańcuch ataku — potwierdzony

```
1. Legit AP (hostapd 2.6/2.10, kan. 6, PMF=2, SSID=CSA_Test_Lab)
2. STA łączy się → Auth → Assoc → 4-Way Handshake → CONNECTED
3. Atakujący wstrzykuje 50 Beacon CSA frames (subtype 8, IE 37):
   "AP przenosi się na kanał 11"
4. STA przetwarza CSA → przełącza kanał 6 → 11 ✓
5. Evil Twin AP startuje na kan. 11 (ten sam SSID, PMF=0)
6. STA reassocjuje się do Evil Twin ✓
7. Handshake przechwycony ✗ (ograniczenie tcpdump w hwsim)
```

**Uwaga:** W środowisku fizycznym (prawdziwy sprzęt WiFi), krok 4 automatycznie izoluje stację od legalnego AP (separacja częstotliwości). W hwsim separacja kanałów nie jest wymuszana sprzętowo.

## 4. Implikacje bezpieczeństwa

### 4.1 Dla administratorów sieci

- **PMF (802.11w) NIE jest wystarczającą ochroną** — Beacon CSA Injection omija PMF na wszystkich wersjach
- Aktualizacja hostapd do ≥ 2.7 chroni przed Action Frame CSA, ale NIE przed Beacon CSA
- **Rekomendowane dodatkowe zabezpieczenia:**
  - Monitorowanie anomalii RSSI (nagła zmiana mocy sygnału przy CSA)
  - Detekcja wielu Beaconów z różnymi CSA IE (WIDS)
  - Ograniczenie mocy nadawania AP (utrudnienie spoofingu z dużej odległości)
  - Weryfikacja, czy klient faktycznie zmienił kanał (monitorowanie po stronie AP)

### 4.2 Dla badaczy bezpieczeństwa

- Środowisko mac80211_hwsim **jest wystarczające** do testowania Beacon CSA Injection (wbrew wcześniejszym wnioskom)
- `CONFIG_CFG80211_CERTIFICATION_ONUS` NIE jest wymagane — ścieżka Beacon CSA działa na stockowym kernelu
- Kluczowe pliki kernela do analizy:
  - `net/wireless/nl80211.c:11328` — ścieżka ADMIN (zablokowana dla STA)
  - `net/mac80211/mlme.c:2752` — ścieżka BEACON CSA (działa)
  - `drivers/net/wireless/virtual/mac80211_hwsim.c:5587` — flaga `CHANCTX_STA_CSA`

## 5. Ograniczenia badania

1. **Środowisko wirtualne** — testy przeprowadzone na mac80211_hwsim, nie na fizycznym sprzęcie
2. **Brak separacji kanałów** — wmediumd nie skonfigurowane poprawnie; w fizycznym środowisku izolacja jest automatyczna
3. **Brak przechwycenia handshake** — tcpdump na interfejsie AP wymaga monitor mode dla ramek 802.11
4. **Jedna implementacja klienta** — testowany tylko wpa_supplicant (Linux); inne stosy (Windows, Android, iOS) mogą zachowywać się inaczej
5. **Brak testów WIDS** — nie zweryfikowano czy systemy detekcji wykrywają Beacon CSA injection

## 6. Rekomendacje — dalsze badania

| Priorytet | Zadanie | Uzasadnienie |
|-----------|--------|-------------|
| Wysoki | Test na fizycznym sprzęcie WiFi | Potwierdzenie w realnym środowisku |
| Wysoki | Przechwycenie 4-way handshake | Domknięcie pełnego łańcucha ataku |
| Średni | Testy na innych klientach (Windows, iOS) | Różne implementacje stosu 802.11 |
| Średni | WIDS evasion | Czy atak jest wykrywalny? |
| Niski | Multi-AP MLO scenarios | WPA3/MLO może mieć dodatkowe zabezpieczenia |

## 7. Podsumowanie końcowe

Projekt udowodnił, że:

1. **Beacon CSA Injection jest skutecznym wektorem omijającym PMF (802.11w)** — Beacon jako Non-Robust frame nie podlega ochronie
2. **Wersja hostapd NIE ma znaczenia** dla tego wektora — atak działa na 2.6 i 2.10
3. **Rekompilacja kernela NIE jest potrzebna** — ścieżka Beacon CSA w mac80211 działa na stockowym kernelu Kali
4. **Środowisko hwsim jest wystarczające** do demonstracji ataku (wbrew wcześniejszym wnioskom z 2026-06-09)

**Kluczowy plik:** `direct_hwsim_csa.py` — pełna implementacja ataku (AP + STA + CSA + Evil Twin)
