# 04 — Atak: Deauth Spoofing

**Data:** 30-31 maja 2026  

## 1. Opis ataku

Atak Deauth Spoofing polega na wysłaniu do stacji-klienta sfałszowanej ramki deauthentication (802.11 subtype 12), podszywającej się pod legalny Access Point. Ramka deauthentication jest klasyfikowana przez 802.11w jako **Robust Management Frame** — powinna być chroniona przez PMF.

Mechanizm PMF chroni ramkę deauth poprzez dodanie do niej Message Integrity Code (MIC), obliczonego przy użyciu klucza IGTK (Integrity Group Temporal Key). Klient po otrzymaniu ramki deauth weryfikuje MIC — jeśli jest niepoprawny lub go brak, ramka jest odrzucana.

## 2. Implementacja

Ramka deauth konstruowana jest przy użyciu biblioteki Scapy:

```python
from scapy.all import RadioTap, Dot11, Dot11Deauth, sendp

frame = RadioTap() / Dot11(
    type=0, subtype=12,       # Management / Deauthentication
    addr1='{target_mac}',     # Destination = stacja-ofiara
    addr2='{ap_mac}',         # Source = sfałszowany adres AP
    addr3='{ap_mac}',         # BSSID
) / Dot11Deauth(reason=7)     # Reason: Class 3 frame from nonassociated STA

sendp(frame, iface='wlan0', count=3, inter=0.1, verbose=True)
```

Atakujący NIE dodaje MIC do ramki, ponieważ nie zna klucza IGTK — symuluje tym samym realny scenariusz, w którym atakujący spoza sieci próbuje rozłączyć klienta.

## 3. Wyniki

| Parametr | Wartość |
|----------|---------|
| Liczba wysłanych ramek | 3 |
| Interwał | 100ms |
| Hostapd | 2.6 i 2.10 |
| Status stacji przed atakiem | ASSOCIATED |
| Status stacji po ataku | STILL ASSOCIATED |

```
=== Post-Attack Association Check ===
  sta1: STILL ASSOCIATED

[PASS] PMF protection working.
       Unprotected deauth frame was rejected by station.
```

**Wynik:** Atak **NIESKUTECZNY**. Stacja odrzuciła sfałszowane ramki deauth. PMF działa poprawnie.

## 4. Analiza

Ramki deauth zostały wysłane (scapy potwierdziło transmisję przez `>` w output), ale stacja je zignorowała. Wireshark potwierdza, że wysłane ramki nie zawierają elementu MIC (Message Integrity Code), który jest wymagany dla ramek Robust Management przy PMF=required.

Brak MIC w ramce deauth powoduje, że stacja (wpa_supplicant z `ieee80211w=2`) odrzuca ramkę na podstawie weryfikacji integralności. Jest to zgodne ze specyfikacją 802.11w.

---

**[✗ SCREENSHOT: Wireshark — ramka deauth wysłana przez atakującego (bez MIC)]**  
**[✗ SCREENSHOT: Wireshark — ramka deauth z poprawnym MIC (dla porównania, z legalnego AP)]**  
**[✗ SCREENSHOT: Terminal — output test_pmf.py pokazujący PASS]**
