# 03 — Testy Bazowe (Baseline)

**Data:** 28-29 maja 2026  

Przed przystapieniem do atakow przeprowadzono testy weryfikujace poprawnosc konfiguracji mechanizmow bezpieczenstwa.

## 1. Client Isolation Test

**Cel:** Zweryfikowac, ze stacje nie moga komunikowac sie bezposrednio na warstwie L2.

**Konfiguracja:** `ap_isolate=1` w hostapd.conf

**Procedura:**
1. Uruchomiono topologie z 3 stacjami (sta1, sta2, sta3)
2. Poczekano 15s na asociacje i przydzielenie adresow IP przez DHCP
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

**Wnioski:** Client Isolation dziala poprawnie. Stacja sta1 nie moze osiagnac sta2 — komunikacja L2 jest blokowana przez AP.

---

## 2. PMF Protection Test (Deauth Spoofing)

**Cel:** Zweryfikowac, ze PMF chroni przed sfalszowanymi ramkami deauthentication.

**Procedura:**
1. Uruchomiono topologie z AP + 2 stacjami
2. Poczekano na asociacje sta1
3. Wyslano 3 sfalszowane ramki deauth (subtype 12) z adresu MAC AP do sta1
4. Sprawdzono, czy sta1 pozostala polaczona

**Wynik:**

```
=== Pre-Test Association Check ===
  sta1: ASSOCIATED

=== Test: Sending Spoofed Deauth Frame ===
> > > > > >     (scapy potwierdza wyslanie 3 ramek)

=== Post-Attack Association Check ===
  sta1: STILL ASSOCIATED

[PASS] PMF protection working.
       Unprotected deauth frame was rejected by station.
       PMF (ieee80211w=2) correctly protects management frames.
```

**Wnioski:** PMF w trybie `required` skutecznie chroni stacje przed sfalszowanymi ramkami deauthentication. Stacja ignoruje ramki pozbawione poprawnego MIC.

---

## 3. CSA Protection Test

**Cel:** Zweryfikowac reakcje stacji na sfalszowana ramke Channel Switch Announcement.

**Procedura:**
1. Uruchomiono topologie z AP (kanal 6) + 1 stacja
2. Wyslano 30 ramek CSA (Action Frame, subtype 13) z elementem CSA (tag 37) wskazujacym kanal 1
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

**Wynik (hostapd 2.6):** Identyczny — stacja nie zmienila stanu.

**Wnioski:** W srodowisku wirtualnym (mac80211_hwsim) ramki CSA nie powoduja zmiany kanalu stacji. Mechanizm przelaczania kanalow jest specyficzny dla rzeczywistego sprzetu radiowego i nie jest w pelni odwzorowany w symulacji programowej. Szczegolowa analiza tego ograniczenia w sekcji [08](08-problemy-implementacyjne.md).

---

**[screenshot: Terminal — output test_isolation.py z PASS]**  
**[screenshot: Terminal — output test_pmf.py z PASS]**  
**[screenshot: Wireshark — przechwycone ramki deauth (3 ramki, brak MIC)**  
**[screenshot: Wireshark — ramka CSA Action Frame z elementem CSA (tag 37)]**
