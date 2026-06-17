# 01 — Metodologia Badan

**Data:** 25-26 maja 2026  

## 1. Model zagrozenia

Badania prowadzono w oparciu o nastepujacy model atakujacego:

```
Atakujacy (bez kluczy PMF):
  - Moze nasluchiwac ramki zarzadzania (Beacon, Probe)
  - Moze wysylac sfalszowane ramki zarzadzania (spoofing adresu MAC AP)
  - NIE posiada kluczy IGTK/PTK — nie moze wygenerowac poprawnego MIC
  - NIE moze wysylac chronionych ramek Robust Management (Deauth, Disassoc)
  
Cel ataku:
  - Zmusic klienta do opuszczenia legalnego AP
  - Przechwycic 4-way handshake na Evil Twin AP (w przypadku CSA)
  - Wykazac podatnosc w implementacji PMF
```

## 2. Ramy prawne i etyczne

Wszystkie testy przeprowadzono w izolowanym srodowisku laboratoryjnym:
- Siec WiFi: wirtualna (mac80211_hwsim + Mininet-WiFi)
- Brak emisji w eterze radiowym
- Brak wplywu na zewnetrzne sieci i urzadzenia

## 3. Metodyka testowania

### 3.1 Testy bazowe (Baseline)

Kazdy test poprzedzono weryfikacja stanu bazowego:

1. **Client Isolation** — weryfikacja, ze stacje nie moga sie komunikowac bezposrednio (ap_isolate=1)
2. **PMF Protection** — weryfikacja, ze sfalszowana ramka deauth jest odrzucana przez stacje
3. **CSA Protection** — weryfikacja reakcji stacji na sfalszowana ramke CSA

### 3.2 Ataki

1. **Deauth Spoofing** — wysylanie sfalszowanych ramek deauthentication (subtype 12) z adresu AP
2. **SA Query Flood** — zalewanie stacji ramkami deauth w celu wyczerpania mechanizmu SA Query
3. **CSA Injection** — wysylanie sfalszowanych ramek Channel Switch Announcement (subtype 13, Action Frame)

### 3.3 Kryteria sukcesu

Atak uznaje sie za **skuteczny** gdy:
- Deauth spoofing: stacja rozlacza sie po otrzymaniu sfalszowanej ramki
- SA Query Flood: stacja rozlacza sie po floodzie (timeout mechanizmu SA Query)
- CSA Injection: stacja zmienia kanal na wskazany w sfalszowanej ramce CSA

## 4. Narzedzia

| Narzedzie | Wersja | Zastosowanie |
|-----------|--------|-------------|
| Kali Linux | 2026.2 | System operacyjny laboratorium |
| Mininet-WiFi | 2.7 (master) | Emulacja topologii WiFi |
| mac80211_hwsim | Kernel 6.x | Wirtualne interfejsy radiowe |
| hostapd | 2.6 / 2.10 | AP (Access Point) |
| wpa_supplicant | 2.10 | Klient WiFi |
| Scapy | 2.7.01 | Generowanie i wysylanie ramek |
| Wireshark | - | Analiza przechwyconych pakietow |
| Kismet | - | Wireless IDS |

---

**[screenshot: Diagram topologii laboratorium — AP + 3 stacje]**  
**[screenshot: Wireshark — przykladowa ramka Deauth z widocznym brakiem MIC]**
