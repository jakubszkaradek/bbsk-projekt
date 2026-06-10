# 01 — Metodologia Badań

**Data:** 25-26 maja 2026  

## 1. Model zagrożenia

Badania prowadzono w oparciu o następujący model atakującego:

```
Atakujący (bez kluczy PMF):
  - Może nasłuchiwać ramki zarządzania (Beacon, Probe)
  - Może wysyłać sfałszowane ramki zarządzania (spoofing adresu MAC AP)
  - NIE posiada kluczy IGTK/PTK — nie może wygenerować poprawnego MIC
  - NIE może wysyłać chronionych ramek Robust Management (Deauth, Disassoc)
  
Cel ataku:
  - Zmusić klienta do opuszczenia legalnego AP
  - Przechwycić 4-way handshake na Evil Twin AP (w przypadku CSA)
  - Wykazać podatność w implementacji PMF
```

## 2. Ramy prawne i etyczne

Wszystkie testy przeprowadzono w izolowanym środowisku laboratoryjnym:
- Sieć WiFi: wirtualna (mac80211_hwsim + Mininet-WiFi)
- Brak emisji w eterze radiowym
- Brak wpływu na zewnętrzne sieci i urządzenia

## 3. Metodyka testowania

### 3.1 Testy bazowe (Baseline)

Każdy test poprzedzono weryfikacją stanu bazowego:

1. **Client Isolation** — weryfikacja, że stacje nie mogą się komunikować bezpośrednio (ap_isolate=1)
2. **PMF Protection** — weryfikacja, że sfałszowana ramka deauth jest odrzucana przez stację
3. **CSA Protection** — weryfikacja reakcji stacji na sfałszowaną ramkę CSA

### 3.2 Ataki

1. **Deauth Spoofing** — wysyłanie sfałszowanych ramek deauthentication (subtype 12) z adresu AP
2. **SA Query Flood** — zalewanie stacji ramkami deauth w celu wyczerpania mechanizmu SA Query
3. **CSA Injection** — wysyłanie sfałszowanych ramek Channel Switch Announcement (subtype 13, Action Frame)

### 3.3 Kryteria sukcesu

Atak uznaje się za **skuteczny** gdy:
- Deauth spoofing: stacja rozłącza się po otrzymaniu sfałszowanej ramki
- SA Query Flood: stacja rozłącza się po floodzie (timeout mechanizmu SA Query)
- CSA Injection: stacja zmienia kanał na wskazany w sfałszowanej ramce CSA

## 4. Narzędzia

| Narzędzie | Wersja | Zastosowanie |
|-----------|--------|-------------|
| Kali Linux | 2026.2 | System operacyjny laboratorium |
| Mininet-WiFi | 2.7 (master) | Emulacja topologii WiFi |
| mac80211_hwsim | Kernel 6.x | Wirtualne interfejsy radiowe |
| hostapd | 2.6 / 2.10 | AP (Access Point) |
| wpa_supplicant | 2.10 | Klient WiFi |
| Scapy | 2.7.01 | Generowanie i wysyłanie ramek |
| Wireshark | - | Analiza przechwyconych pakietów |
| Kismet | - | Wireless IDS |

---

**[✗ SCREENSHOT: Diagram topologii laboratorium — AP + 3 stacje]**  
**[✗ SCREENSHOT: Wireshark — przykładowa ramka Deauth z widocznym brakiem MIC]**
