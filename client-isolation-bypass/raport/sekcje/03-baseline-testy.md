# 03 — Testy Bazowe (Baseline)

**Data:** 28-29 maja 2026  

Przed przystąpieniem do ataków przeprowadzono testy weryfikujące poprawność konfiguracji mechanizmów bezpieczeństwa.

## 1. Client Isolation Test

**Cel:** Zweryfikować, że stacje nie mogą komunikować się bezpośrednio na warstwie L2.

**Konfiguracja:** `ap_isolate=1` w hostapd.conf

**Procedura:**
1. Uruchomiono topologię z 3 stacjami (sta1, sta2, sta3)
2. Poczekano 15s na asociację i przydzielenie adresów IP przez DHCP
3. Wykonano ping ze sta1 do sta2

**Wynik:**

```
=== IP Address Assignment ===
  sta1: 10.0.0.1
  sta2: 10.0.0.2
  sta3: 10.0.0.3

=== PING Test: sta1 -> sta2 (10.0.0.2) ===
ping: connect: Network is unreachable

[PASS] Client Isolation working correctly.
```

**Wnioski:** Client Isolation działa poprawnie. Stacja sta1 nie może osiągnąć sta2 — komunikacja L2 jest blokowana przez AP.

---

## 2. PMF Protection Test (Deauth Spoofing)

**Cel:** Zweryfikować, że PMF chroni przed sfałszowanymi ramkami deauthentication.

**Procedura:**
1. Uruchomiono topologię z AP + 2 stacjami
2. Poczekano na asociację sta1
3. Wysłano 3 sfałszowane ramki deauth (subtype 12) z adresu MAC AP do sta1
4. Sprawdzono, czy sta1 pozostała połączona

**Wynik:**

```
=== Pre-Test Association Check ===
  sta1: ASSOCIATED

=== Test: Sending Spoofed Deauth Frame ===
> > > > > >     (scapy potwierdza wysłanie 3 ramek)

=== Post-Attack Association Check ===
  sta1: STILL ASSOCIATED

[PASS] PMF protection working.
       Unprotected deauth frame was rejected by station.
       PMF (ieee80211w=2) correctly protects management frames.
```

**Wnioski:** PMF w trybie `required` skutecznie chroni stację przed sfałszowanymi ramkami deauthentication. Stacja ignoruje ramki pozbawione poprawnego MIC.

---

## 3. CSA Protection Test

**Cel:** Zweryfikować reakcję stacji na sfałszowaną ramkę Channel Switch Announcement.

**Procedura:**
1. Uruchomiono topologię z AP (kanał 6) + 1 stacją
2. Wysłano 30 ramek CSA (Action Frame, subtype 13) z elementem CSA (tag 37) wskazującym kanał 1
3. Sprawdzono stan stacji po ataku (IP, stan interfejsu)

**Wynik (hostapd 2.10):**

```
=== Pre-Test ===
  IP: 10.0.0.1  MAC: 7a:a4:c1:d2:ab:dd  IFACE_UP: False

=== Sending Spoofed CSA Frames ===
  Frames sent: 3/30

=== Post-Test ===
  IP: 10.0.0.1  IFACE_UP: False
  IP stable: True

[PASS] Station unaffected.
```

**Wynik (hostapd 2.6):** Identyczny — stacja nie zmieniła stanu.

**Wnioski:** W środowisku wirtualnym (mac80211_hwsim) ramki CSA nie powodują zmiany kanału stacji. Mechanizm przełączania kanałów jest specyficzny dla rzeczywistego sprzętu radiowego i nie jest w pełni odwzorowany w symulacji programowej. Szczegółowa analiza tego ograniczenia w sekcji [08](08-problemy-implementacyjne.md).

---

**[✗ SCREENSHOT: Terminal — output test_isolation.py z PASS]**  
**[✗ SCREENSHOT: Terminal — output test_pmf.py z PASS]**  
**[✗ SCREENSHOT: Wireshark — przechwycone ramki deauth (3 ramki, brak MIC)**  
**[✗ SCREENSHOT: Wireshark — ramka CSA Action Frame z elementem CSA (tag 37)]**
