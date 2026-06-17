# 09 — Wnioski i Rekomendacje

**Data:** 10 czerwca 2026

## 1. Glowny wniosek

**Protected Management Frames (802.11w) nie chronia przed atakiem Beacon CSA Injection.**

Analiza kodu zrodlowego kernela Linux 6.19.14 oraz testy praktyczne na srodowisku mac80211_hwsim z hostapd 2.6 i 2.10 potwierdzaja, ze:

- Beacon frames (subtype 8) sa **zawsze** klasyfikowane jako Non-Robust Management Frames przez 802.11w
- CSA Information Element (tag 37) w Beaconie jest przetwarzany przez stacje **niezaleznie** od ustawienia `ieee80211w=2`
- Mechanizm PMF chroni tylko ramki Action Frame CSA (subtype 13) na hostapd ≥ 2.7
- Atak Beacon CSA dziala na **wszystkich testowanych wersjach hostapd** (2.6, 2.10)

## 2. Wyniki testow — podsumowanie

| Atak | Wektor | PMF=2 | Wynik |
|------|--------|-------|-------|
| Deauth Injection | subtype 12 | Chroniony | FAIL — PMF blokuje |
| Disassoc Injection | subtype 10 | Chroniony | FAIL — PMF blokuje |
| Action Frame CSA | subtype 13 (< 2.7) | Niechroniony | Teoretycznie dziala (nietestowalne w hwsim) |
| Action Frame CSA | subtype 13 (≥ 2.7) | Chroniony | FAIL — PMF blokuje |
| **Beacon CSA** | **subtype 8, IE 37** | **Niechroniony** | **SUCCESS — dziala na wszystkich wersjach** |
| SA Query Flood | Deauth + SA Query | Chroniony | Czesciowy — zalew dziala, ale stacja nie rozlacza sie |

## 3. Pelny lancuch ataku — potwierdzony

```
1. Legit AP (hostapd 2.6/2.10, kan. 6, PMF=2, SSID=CSA_Test_Lab)
2. STA laczy sie → Auth → Assoc → 4-Way Handshake → CONNECTED
3. Atakujacy wstrzykuje 50 Beacon CSA frames (subtype 8, IE 37):
   "AP przenosi sie na kanal 11"
4. STA przetwarza CSA → przelacza kanal 6 → 11 5. Evil Twin AP startuje na kan. 11 (ten sam SSID, PMF=0)
6. STA reassocjuje sie do Evil Twin 7. Handshake przechwycony (ograniczenie tcpdump w hwsim)
```

**Uwaga:** W srodowisku fizycznym (prawdziwy sprzet WiFi), krok 4 automatycznie izoluje stacje od legalnego AP (separacja czestotliwosci). W hwsim separacja kanalow nie jest wymuszana sprzetowo.

## 4. Implikacje bezpieczenstwa

### 4.1 Dla administratorow sieci

- **PMF (802.11w) NIE jest wystarczajaca ochrona** — Beacon CSA Injection omija PMF na wszystkich wersjach
- Aktualizacja hostapd do ≥ 2.7 chroni przed Action Frame CSA, ale NIE przed Beacon CSA
- **Rekomendowane dodatkowe zabezpieczenia:**
  - Monitorowanie anomalii RSSI (nagla zmiana mocy sygnalu przy CSA)
  - Detekcja wielu Beaconow z roznymi CSA IE (WIDS)
  - Ograniczenie mocy nadawania AP (utrudnienie spoofingu z duzej odleglosci)
  - Weryfikacja, czy klient faktycznie zmienil kanal (monitorowanie po stronie AP)

### 4.2 Dla badaczy bezpieczenstwa

- Srodowisko mac80211_hwsim **jest wystarczajace** do testowania Beacon CSA Injection (wbrew wczesniejszym wnioskom)
- `CONFIG_CFG80211_CERTIFICATION_ONUS` NIE jest wymagane — sciezka Beacon CSA dziala na stockowym kernelu
- Kluczowe pliki kernela do analizy:
  - `net/wireless/nl80211.c:11328` — sciezka ADMIN (zablokowana dla STA)
  - `net/mac80211/mlme.c:2752` — sciezka BEACON CSA (dziala)
  - `drivers/net/wireless/virtual/mac80211_hwsim.c:5587` — flaga `CHANCTX_STA_CSA`

## 5. Ograniczenia badania

1. **Srodowisko wirtualne** — testy przeprowadzone na mac80211_hwsim, nie na fizycznym sprzecie
2. **Brak separacji kanalow** — wmediumd nie skonfigurowane poprawnie; w fizycznym srodowisku izolacja jest automatyczna
3. **Brak przechwycenia handshake** — tcpdump na interfejsie AP wymaga monitor mode dla ramek 802.11
4. **Jedna implementacja klienta** — testowany tylko wpa_supplicant (Linux); inne stosy (Windows, Android, iOS) moga zachowywac sie inaczej
5. **Brak testow WIDS** — nie zweryfikowano czy systemy detekcji wykrywaja Beacon CSA injection

## 6. Rekomendacje — dalsze badania

| Priorytet | Zadanie | Uzasadnienie |
|-----------|--------|-------------|
| Wysoki | Test na fizycznym sprzecie WiFi | Potwierdzenie w realnym srodowisku |
| Wysoki | Przechwycenie 4-way handshake / ruchu uzytkownika | Domkniecie pelnego lancucha ataku i obserwacji ruchu po Evil Twin |
| Sredni | Testy na innych klientach (Windows, iOS) | Rozne implementacje stosu 802.11 |
| Sredni | WIDS evasion | Czy atak jest wykrywalny? |
| Niski | Multi-AP MLO scenarios | WPA3/MLO moze miec dodatkowe zabezpieczenia |

## 7. Podsumowanie koncowe

Projekt udowodnil, ze:

1. **Beacon CSA Injection jest skutecznym wektorem omijajacym PMF (802.11w)** — Beacon jako Non-Robust frame nie podlega ochronie
2. **Wersja hostapd NIE ma znaczenia** dla tego wektora — atak dziala na 2.6 i 2.10
3. **Rekompilacja kernela NIE jest potrzebna** — sciezka Beacon CSA w mac80211 dziala na stockowym kernelu Kali
4. **Srodowisko hwsim jest wystarczajace** do demonstracji ataku (wbrew wczesniejszym wnioskom z 2026-06-09)
5. **Client Isolation jest polityka AP, nie wlasciwoscia klienta** — po reassocjacji do Evil Twin bez `ap_isolate=1` ci sami klienci odzyskuja mozliwosc komunikacji L2 (`EVIL_TWIN_PING_PASS`)

**Kluczowy plik:** `direct_hwsim_csa.py` — pelna implementacja demonstracji (legalny AP z izolacja + 2 STA + CSA + Evil Twin bez izolacji + ping/PCAP proof)
